from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import datetime

from ..core.database import supabase
from ..core.logger import log
from ..services.sms_service import sms_service
from ..services.followup_service import followup_service
from ..services.insurance_service import insurance_service
from ..services.noshow_service import noshow_service
from ..services.waitlist_service import waitlist_service
from ..services.revenue_service import revenue_service
from ..services.recall_service import recall_service
from ..services.email_service import email_service
import asyncio
from ..core.database import get_clinic_with_billing, update_clinic_billing
from ..core.logger import log

scheduler = AsyncIOScheduler()

async def run_cron_with_lock(lock_key: str, lease_seconds: int, cron_func):
    """
    Acquires a distributed database lock from Supabase before running the cron function.
    Fails safely and runs the job if the lock table or RPC is unconfigured/missing.
    """
    try:
        # Execute the database lock acquisition function using run_in_executor to avoid blocking the ASGI loop
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.rpc("acquire_distributed_lock", {
                "lock_key": lock_key,
                "lease_seconds": lease_seconds
            }).execute()
        )
        
        lock_acquired = res.data if res else False
        if lock_acquired:
            log.info(f"Acquired distributed lock '{lock_key}' for {lease_seconds}s.")
            try:
                await cron_func()
            finally:
                # Release lock after execution
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.rpc("release_distributed_lock", {
                        "lock_key": lock_key
                    }).execute()
                )
                log.info(f"Released distributed lock '{lock_key}'.")
        else:
            log.info(f"Lock '{lock_key}' is held by another instance. Skipping execution.")
            
    except Exception as e:
        # Self-healing degradation: if migration has not been run or database fails, execute the cron anyway.
        log.warning(f"Distributed lock check failed for '{lock_key}': {str(e)} - falling back to unlocked run.")
        try:
            await cron_func()
        except Exception as fallback_err:
            log.error(f"Fallback execution failed for '{lock_key}': {fallback_err}")
            # Fire Slack alert for critical cron failures
            try:
                from ..services.slack_service import slack_service
                await slack_service.alert(
                    f"Cron job '{lock_key}' failed",
                    level="error",
                    details={"error": str(fallback_err), "job": lock_key}
                )
            except Exception:
                pass


async def get_all_clinics():
    res = supabase.table("clinics").select("id").eq("is_active", True).execute()
    return [c["id"] for c in (res.data or [])]

async def process_reminders():
    log.info("Running process_reminders job...")
    clinics = await get_all_clinics()
    now = datetime.datetime.now(datetime.timezone.utc)
    in24h = now + datetime.timedelta(hours=24)
    
    for cid in clinics:
        try:
            # Find appointments in next 24 hours that haven't received a reminder
            res = supabase.table("appointments").select("id").eq("clinic_id", cid).in_("status", ["scheduled", "confirmed"]).eq("reminder_sent", False).gte("datetime", now.isoformat()).lte("datetime", in24h.isoformat()).execute()
            appts = res.data or []
            if not appts:
                continue
                
            # Log job record before action (crash-safe)
            job_res = supabase.table("jobs").insert({
                "clinic_id": cid,
                "job_type": "send_reminder",
                "payload": {"appointments_count": len(appts), "appt_ids": [a["id"] for a in appts]},
                "status": "processing"
            }).execute()
            job_id = job_res.data.get("id") if isinstance(job_res.data, dict) else (job_res.data[0].get("id") if (job_res.data and len(job_res.data) > 0) else None)
            
            failed_appts = []
            for appt in appts:
                try:
                    await sms_service.send_reminder(appt["id"])
                except Exception as inner_e:
                    failed_appts.append({"id": appt["id"], "error": str(inner_e)})
            
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if job_id:
                if failed_appts:
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": f"Failed reminders: {failed_appts}",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
                else:
                    supabase.table("jobs").update({
                        "status": "done",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
                    
        except Exception as e:
            log.error(f"[process_reminders] clinicId={cid} error: {str(e)}")

async def process_followups():
    log.info("Running process_followups job...")
    clinics = await get_all_clinics()
    for cid in clinics:
        try:
            # Log job record before action (crash-safe)
            job_res = supabase.table("jobs").insert({
                "clinic_id": cid,
                "job_type": "post_visit_followup",
                "payload": {"action": "process_followups"},
                "status": "processing"
            }).execute()
            job_id = job_res.data.get("id") if isinstance(job_res.data, dict) else (job_res.data[0].get("id") if (job_res.data and len(job_res.data) > 0) else None)
            
            res = await followup_service.process_followups(cid)
            
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if job_id:
                if res.get("success"):
                    supabase.table("jobs").update({
                        "status": "done",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
                else:
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": res.get("error"),
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
        except Exception as e:
            log.error(f"[scheduler] process_followups clinicId={cid} error: {str(e)}")

async def process_insurance_verifications():
    log.info(f"[scheduler] Running process_insurance_verifications job at {datetime.datetime.now()}")
    clinics = await get_all_clinics()
    for cid in clinics:
        try:
            # Log job record before action (crash-safe)
            job_res = supabase.table("jobs").insert({
                "clinic_id": cid,
                "job_type": "insurance_check",
                "payload": {"action": "process_verifications"},
                "status": "processing"
            }).execute()
            job_id = job_res.data.get("id") if isinstance(job_res.data, dict) else (job_res.data[0].get("id") if (job_res.data and len(job_res.data) > 0) else None)
            
            res = await insurance_service.process_verifications(cid)
            
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if job_id:
                if res.get("success"):
                    supabase.table("jobs").update({
                        "status": "done",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
                else:
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": res.get("error"),
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
        except Exception as e:
            log.error(f"[scheduler] process_insurance_verifications clinicId={cid} error: {str(e)}")

async def process_noshow_predictions():
    log.info(f"[scheduler] Running process_noshow_predictions job at {datetime.datetime.now()}")
    clinics = await get_all_clinics()
    tomorrow = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).isoformat()
    for cid in clinics:
        try:
            # Log job record before action (crash-safe)
            job_res = supabase.table("jobs").insert({
                "clinic_id": cid,
                "job_type": "noshow_prediction",
                "payload": {"date": tomorrow},
                "status": "processing"
            }).execute()
            job_id = job_res.data.get("id") if isinstance(job_res.data, dict) else (job_res.data[0].get("id") if (job_res.data and len(job_res.data) > 0) else None)
            
            res = await noshow_service.process_noshow_confirmations(cid, tomorrow)
            
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            if job_id:
                if res.get("success"):
                    supabase.table("jobs").update({
                        "status": "done",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
                else:
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": res.get("error"),
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
        except Exception as e:
            log.error(f"[scheduler] process_noshow_predictions clinicId={cid} error: {str(e)}")

async def process_recalls():
    log.info(f"[scheduler] Running process_recalls job at {datetime.datetime.now()}")
    clinics = await get_all_clinics()
    for cid in clinics:
        try:
            # Log job record before action (crash-safe)
            job_res = supabase.table("jobs").insert({
                "clinic_id": cid,
                "job_type": "recall_batch",
                "payload": {"action": "process_recalls"},
                "status": "processing"
            }).execute()
            job_id = job_res.data.get("id") if isinstance(job_res.data, dict) else (job_res.data[0].get("id") if (job_res.data and len(job_res.data) > 0) else None)
            
            res = await recall_service.get_recall_candidates(cid)
            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            if res.get("success") and res.get("data"):
                candidates = res["data"]
                # Limit to max 20 per day to avoid spamming
                for candidate in candidates[:20]:
                    try:
                        await recall_service.initiate_recall(cid, candidate["id"])
                    except Exception as inner_e:
                        log.error(f"[scheduler] process_recalls inner recall error for patient={candidate['id']}: {str(inner_e)}")
                
                if job_id:
                    supabase.table("jobs").update({
                        "status": "done",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
            elif res.get("success"):
                if job_id:
                    supabase.table("jobs").update({
                        "status": "done",
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
            else:
                if job_id:
                    supabase.table("jobs").update({
                        "status": "failed",
                        "error_message": res.get("error"),
                        "ran_at": now_iso
                    }).eq("id", job_id).execute()
        except Exception as e:
            log.error(f"[scheduler] process_recalls clinicId={cid} error: {str(e)}")

async def process_trials():
    log.info(f"[scheduler] Running process_trials job at {datetime.datetime.now()}")
    # Fetch all clinics that are on trial plan
    # Since billing state might be in JSONB, we'll fetch all clinics and filter in python
    # to be safe and compatible with our fallback logic
    res = supabase.table("clinics").select("id, owner_email").execute()
    clinics = res.data or []
    
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for c in clinics:
        cid = c["id"]
        try:
            clinic_details = get_clinic_with_billing(cid)
            plan = clinic_details.get("plan")
            is_active = clinic_details.get("is_active", True)
            
            if plan != "trial":
                continue
                
            trial_ends_str = clinic_details.get("trial_ends_at")
            if not trial_ends_str:
                continue
                
            trial_ends = datetime.datetime.fromisoformat(trial_ends_str.replace("Z", "+00:00"))
            time_left = trial_ends - now
            days_left = time_left.days
            
            trial_reminder_sent = clinic_details.get("trial_reminder_sent", False)
            trial_ended_sent = clinic_details.get("trial_ended_sent", False)
            owner_email = clinic_details.get("owner_email")
            
            # 1. Day 10 Reminder (4 days left)
            if 0 < days_left <= 4 and not trial_reminder_sent:
                log.info(f"[scheduler] Sending trial reminder to {owner_email}")
                await email_service.send_trial_reminder_email(owner_email, cid, days_left)
                update_clinic_billing(cid, {"trial_reminder_sent": True})
                
            # 2. Day 14 Suspension (trial ended)
            if time_left.total_seconds() < 0 and is_active:
                log.info(f"[scheduler] Trial expired for {owner_email}, suspending clinic")
                update_clinic_billing(cid, {
                    "is_active": False,
                    "stripe_subscription_status": "canceled",
                    "trial_ended_sent": True
                })
                # We also need to update is_active on the root table physically just in case
                from ..core.database import update_clinic
                update_clinic(cid, {"is_active": False})
                
                if not trial_ended_sent:
                    await email_service.send_trial_ended_email(owner_email, cid)
                    
        except Exception as e:
            log.error(f"[scheduler] process_trials clinicId={cid} error: {str(e)}")

async def cleanup_demo_clinics():
    """
    Cron job to clean up sandbox demo clinics after their 7-day trial has ended.
    Deletes all related patients, appointments, calls, and Auth users.
    """
    log.info(f"[scheduler] Running cleanup_demo_clinics job at {datetime.datetime.now()}")
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Find all expired demo clinics
        res = supabase.table("clinics").select("id, owner_email").eq("is_demo", True).lt("trial_ends_at", now).execute()
        expired_clinics = res.data or []
        
        for clinic in expired_clinics:
            cid = clinic["id"]
            owner_email = clinic["owner_email"]
            log.info(f"[scheduler] Deleting expired demo clinic: {cid} ({owner_email})")
            
            # Fetch all user IDs linked to this clinic
            cu_res = supabase.table("clinic_users").select("supabase_user_id").eq("clinic_id", cid).execute()
            user_ids = [row["supabase_user_id"] for row in (cu_res.data or []) if row.get("supabase_user_id")]
            
            # 1. Delete associated users from Supabase Auth
            for uid in user_ids:
                try:
                    supabase.auth.admin.delete_user(uid)
                    log.info(f"[scheduler] Deleted auth user {uid}")
                except Exception as auth_err:
                    log.error(f"[scheduler] Failed to delete auth user {uid}: {auth_err}")
                    
            # 2. Delete child table records manually to bypass potential schema foreign key blockages
            for table in ["calls", "appointments", "patients", "clinic_users", "referrals"]:
                try:
                    col_name = "referrer_clinic_id" if table == "referrals" else "clinic_id"
                    supabase.table(table).delete().eq(col_name, cid).execute()
                except Exception as tbl_err:
                    log.warning(f"[scheduler] cleanup_demo non-critical: Table {table} clean failed: {tbl_err}")
                    
            # 3. Delete the clinic itself
            supabase.table("clinics").delete().eq("id", cid).execute()
            from ..core.database import invalidate_clinic_cache
            invalidate_clinic_cache(cid, owner_email)
            log.info(f"[scheduler] Successfully deleted demo clinic: {cid}")
            
    except Exception as e:
        log.error(f"[scheduler] cleanup_demo_clinics error: {str(e)}")

# Locked cron wrappers
async def process_database_backups():
    log.info(f"[scheduler] Running process_database_backups job at {datetime.datetime.now()}")
    from ..services.backup_service import backup_service
    await backup_service.run_backup()

async def locked_process_database_backups():
    await run_cron_with_lock("lock_process_database_backups", 1800, process_database_backups)

async def locked_process_reminders():
    await run_cron_with_lock("lock_process_reminders", 300, process_reminders)

async def locked_process_followups():
    await run_cron_with_lock("lock_process_followups", 900, process_followups)

async def locked_process_insurance_verifications():
    await run_cron_with_lock("lock_process_insurance_verifications", 900, process_insurance_verifications)

async def locked_process_noshow_predictions():
    await run_cron_with_lock("lock_process_noshow_predictions", 900, process_noshow_predictions)

async def locked_process_recalls():
    await run_cron_with_lock("lock_process_recalls", 1800, process_recalls)

async def locked_process_trials():
    await run_cron_with_lock("lock_process_trials", 900, process_trials)

async def locked_cleanup_demo_clinics():
    await run_cron_with_lock("lock_cleanup_demo_clinics", 900, cleanup_demo_clinics)

async def process_weekly_insights():
    log.info(f"[scheduler] Running process_weekly_insights job at {datetime.datetime.now()}")
    # Fetch all active clinics
    res = supabase.table("clinics").select("id").eq("is_active", True).execute()
    clinics = res.data or []
    for c in clinics:
        try:
            from ..services.insights_service import insights_service
            await insights_service.generate_and_email_weekly_insights(c["id"])
        except Exception as insights_err:
            log.error(f"[scheduler] process_weekly_insights clinicId={c.get('id')} error: {str(insights_err)}")

async def locked_process_weekly_insights():
    await run_cron_with_lock("lock_process_weekly_insights", 3600, process_weekly_insights)

async def process_daily_reports():
    log.info("Running process_daily_reports job...")
    try:
        # Get all active clinics
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics").select("id, name, owner_email").eq("is_active", True).execute()
        )
        clinics = res.data or []
        
        # Calculate yesterday's date range
        now = datetime.datetime.now(datetime.timezone.utc)
        yesterday = now - datetime.timedelta(days=1)
        
        # Start and end of yesterday in ISO format
        yesterday_start = datetime.datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat()
        yesterday_end = datetime.datetime(yesterday.year, yesterday.month, yesterday.day, 23, 59, 59, tzinfo=datetime.timezone.utc).isoformat()
        
        for clinic in clinics:
            cid = clinic["id"]
            owner_email = clinic.get("owner_email")
            if not owner_email:
                continue
                
            # Log job record before action (crash-safe)
            try:
                job_res = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("jobs").insert({
                        "clinic_id": cid,
                        "job_type": "daily_report",
                        "payload": {"date": yesterday.strftime("%Y-%m-%d")},
                        "status": "processing"
                    }).execute()
                )
                job_id = job_res.data.get("id") if isinstance(job_res.data, dict) else (job_res.data[0].get("id") if (job_res.data and len(job_res.data) > 0) else None)
            except Exception as job_err:
                log.error(f"[process_daily_reports] Failed to create job record: {job_err}")
                job_id = None
                
            try:
                # Fetch yesterday's stats
                # calls count
                calls_res = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("calls").select("id").eq("clinic_id", cid).gte("created_at", yesterday_start).lte("created_at", yesterday_end).execute()
                )
                total_calls = len(calls_res.data or [])
                
                # appointments booked by AI count
                appt_res = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("appointments").select("id").eq("clinic_id", cid).eq("booked_by", "ai").gte("created_at", yesterday_start).lte("created_at", yesterday_end).execute()
                )
                total_appts = len(appt_res.data or [])
                
                # revenue events recovered
                rev_res = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: supabase.table("revenue_events").select("amount_cents").eq("clinic_id", cid).gte("created_at", yesterday_start).lte("created_at", yesterday_end).execute()
                )
                total_rev_cents = sum(e.get("amount_cents", 0) for e in (rev_res.data or []))
                rev_dollars = round(total_rev_cents / 100)
                
                stats = {
                    "totalCalls": total_calls,
                    "totalAppointments": total_appts,
                    "revenueRecoveredDollars": rev_dollars
                }
                
                # Send email
                await email_service.send_daily_report(clinic, stats)
                
                if job_id:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: supabase.table("jobs").update({
                            "status": "done",
                            "ran_at": now_iso
                        }).eq("id", job_id).execute()
                    )
            except Exception as inner_e:
                log.error(f"[process_daily_reports] Error processing clinic {cid}: {inner_e}")
                if job_id:
                    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: supabase.table("jobs").update({
                            "status": "failed",
                            "error_message": str(inner_e),
                            "ran_at": now_iso
                        }).eq("id", job_id).execute()
                    )
    except Exception as e:
        log.error(f"[process_daily_reports] Global error: {e}")

async def locked_process_daily_reports():
    await run_cron_with_lock("lock_process_daily_reports", 1800, process_daily_reports)

async def sync_patient_ltv_stats():
    log.info(f"[scheduler] Running sync_patient_ltv_stats job at {datetime.datetime.now(datetime.timezone.utc)}")
    try:
        # Fetch all clinics
        res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("clinics").select("id, monthly_revenue_per_visit").execute()
        )
        clinics = res.data or []
        for clinic in clinics:
            clinic_id = clinic.get("id")
            rev_per_visit = float(clinic.get("monthly_revenue_per_visit") or 150.0)

            # Fetch all appointments for the clinic
            appts_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("appointments").select("patient_id, status, datetime").eq("clinic_id", clinic_id).execute()
            )
            appts = appts_res.data or []

            # Group appointments by patient_id
            patient_appts = {}
            for appt in appts:
                pid = appt.get("patient_id")
                if pid:
                    if pid not in patient_appts:
                        patient_appts[pid] = []
                    patient_appts[pid].append(appt)

            # Fetch all patients for this clinic
            patients_res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("patients").select("id").eq("clinic_id", clinic_id).execute()
            )
            patients = patients_res.data or []

            patient_updates = []
            today = datetime.datetime.now(datetime.timezone.utc).date()

            # Calculate stats for each patient
            for pat in patients:
                pid = pat.get("id")
                p_appts = patient_appts.get(pid, [])

                # Filter completed appointments
                completed_appts = [a for a in p_appts if a.get("status") == "completed"]
                completed_count = len(completed_appts)

                total_revenue = completed_count * rev_per_visit
                avg_visit_value = rev_per_visit if completed_count > 0 else 0.0

                # Sort completed appointments chronologically
                parsed_appts = []
                for a in completed_appts:
                    dt_str = a.get("datetime")
                    if dt_str:
                        try:
                            # parse ISO format or simple date
                            dt = datetime.datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                            parsed_appts.append(dt)
                        except Exception:
                            pass
                parsed_appts.sort()

                # Calculate last visit date and visit frequency
                last_visit_date_str = None
                visit_frequency_days = None

                if parsed_appts:
                    last_visit_date_str = parsed_appts[-1].strftime("%Y-%m-%d")
                    last_visit_date = parsed_appts[-1].date()
                    days_since_last_visit = (today - last_visit_date).days

                    # Churn risk calculation
                    if completed_count >= 5 and days_since_last_visit >= 90:
                        churn_risk_score = 1.00
                    else:
                        # Calculate average frequency in days
                        if len(parsed_appts) >= 2:
                            diffs = [(parsed_appts[i+1] - parsed_appts[i]).days for i in range(len(parsed_appts)-1)]
                            avg_diff = sum(diffs) / len(diffs)
                            visit_frequency_days = int(round(avg_diff))
                            if visit_frequency_days <= 0:
                                visit_frequency_days = 1 # Avoid division by zero/negative
                            
                            churn_risk_score = min(1.0, days_since_last_visit / (visit_frequency_days * 2.5))
                        else:
                            # 1 completed appointment
                            churn_risk_score = min(1.0, days_since_last_visit / 180.0)
                else:
                    churn_risk_score = 0.00

                # Ensure churn_risk_score is rounded and bounds-checked
                churn_risk_score = float(round(max(0.00, min(1.00, churn_risk_score)), 2))

                patient_updates.append({
                    "id": pid,
                    "total_revenue_generated": total_revenue,
                    "average_visit_value": avg_visit_value,
                    "visit_frequency_days": visit_frequency_days,
                    "churn_risk_score": churn_risk_score,
                    "last_visit_date": last_visit_date_str,
                    "completed_count": completed_count
                })

            # Calculate VIP status based on LTV percentile and completed count
            # VIP: top 15% of total_revenue_generated (among patients with >0 revenue) OR completed_count > 10
            valid_revenues = [p["total_revenue_generated"] for p in patient_updates if p["total_revenue_generated"] > 0]
            valid_revenues.sort(reverse=True)
            
            vip_threshold_revenue = float('inf')
            if valid_revenues:
                cutoff_index = int(len(valid_revenues) * 0.15)
                if cutoff_index > 0:
                    vip_threshold_revenue = valid_revenues[cutoff_index - 1]
                else:
                    vip_threshold_revenue = valid_revenues[0]

            for pu in patient_updates:
                is_vip = False
                if pu["completed_count"] > 10:
                    is_vip = True
                elif pu["total_revenue_generated"] > 0 and pu["total_revenue_generated"] >= vip_threshold_revenue:
                    is_vip = True

                # Update the database
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda p_id=pu["id"], payload={
                        "total_revenue_generated": pu["total_revenue_generated"],
                        "average_visit_value": pu["average_visit_value"],
                        "visit_frequency_days": pu["visit_frequency_days"],
                        "churn_risk_score": pu["churn_risk_score"],
                        "is_vip": is_vip,
                        "last_visit_date": pu["last_visit_date"]
                    }: supabase.table("patients").update(payload).eq("id", p_id).execute()
                )

        log.info("[scheduler] Completed sync_patient_ltv_stats successfully.")
    except Exception as e:
        log.error(f"[scheduler] sync_patient_ltv_stats error: {str(e)}")

async def locked_sync_patient_ltv_stats():
    await run_cron_with_lock("lock_sync_patient_ltv_stats", 1800, sync_patient_ltv_stats)

async def refresh_materialized_views():
    log.info("Running refresh_materialized_views...")
    try:
        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.rpc("refresh_materialized_view", {"view_name": "today_appointments_mv"}).execute()
        )
        log.info("Successfully refreshed today_appointments_mv materialized view.")
    except Exception as e:
        log.error(f"Failed to refresh today_appointments_mv: {str(e)}")

async def locked_refresh_materialized_views():
    await run_cron_with_lock("lock_refresh_materialized_views", 180, refresh_materialized_views)

async def purge_expired_data():
    log.info("Running purge_expired_data (7-year HIPAA retention cleanup)...")
    try:
        # Calculate cutoff timestamp (7 years ago)
        cutoff_date = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7 * 365.25)).isoformat()
        
        # 1. Delete expired SMS messages
        sms_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("sms_messages").delete().lt("created_at", cutoff_date).execute()
        )
        sms_deleted = len(sms_res.data) if sms_res.data else 0
        
        # 2. Delete expired calls
        calls_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("calls").delete().lt("created_at", cutoff_date).execute()
        )
        calls_deleted = len(calls_res.data) if calls_res.data else 0
        
        # 3. Delete expired appointments
        appts_res = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: supabase.table("appointments").delete().lt("created_at", cutoff_date).execute()
        )
        appts_deleted = len(appts_res.data) if appts_res.data else 0
        
        log.info(f"HIPAA Purge completed. Deleted: {sms_deleted} SMS, {calls_deleted} calls, {appts_deleted} appointments older than 7 years.")
    except Exception as e:
        log.error(f"Failed to run HIPAA purge_expired_data: {str(e)}")

async def locked_purge_expired_data():
    await run_cron_with_lock("lock_purge_expired_data", 1800, purge_expired_data)

def start_jobs():
    """
    Registers and starts all cron jobs, mirroring the Node.js implementation.
    """
    if scheduler.running:
        log.warning("APScheduler is already running, skipping start_jobs.")
        return
        
    # Clear any existing jobs to prevent duplicates on module reload
    try:
        scheduler.remove_all_jobs()
    except Exception as e:
        log.error(f"Error clearing jobs: {str(e)}")

    scheduler.add_job(locked_process_reminders, CronTrigger(minute="*/15"), id="process_reminders", replace_existing=True) # Every 15 mins
    scheduler.add_job(locked_refresh_materialized_views, CronTrigger(minute="*/15"), id="refresh_materialized_views", replace_existing=True) # Every 15 mins
    scheduler.add_job(locked_purge_expired_data, CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="UTC"), id="purge_expired_data", replace_existing=True) # 3 AM Sunday UTC
    scheduler.add_job(locked_process_followups, CronTrigger(hour=10, minute=0, timezone="UTC"), id="process_followups", replace_existing=True) # 10 AM daily UTC
    scheduler.add_job(locked_process_insurance_verifications, CronTrigger(hour=9, minute=0, timezone="UTC"), id="process_insurance_verifications", replace_existing=True) # 9 AM daily UTC
    scheduler.add_job(locked_process_noshow_predictions, CronTrigger(hour=18, minute=0, timezone="UTC"), id="process_noshow_predictions", replace_existing=True) # 6 PM daily UTC
    scheduler.add_job(locked_process_recalls, CronTrigger(hour=20, minute=0, timezone="UTC"), id="process_recalls", replace_existing=True) # 8 PM daily UTC
    scheduler.add_job(locked_process_trials, CronTrigger(hour=8, minute=0, timezone="UTC"), id="process_trials", replace_existing=True) # 8 AM daily UTC
    scheduler.add_job(locked_cleanup_demo_clinics, CronTrigger(hour=3, minute=0, timezone="UTC"), id="cleanup_demo_clinics", replace_existing=True) # 3 AM daily UTC
    scheduler.add_job(locked_process_database_backups, CronTrigger(hour=2, minute=0, timezone="UTC"), id="process_database_backups", replace_existing=True) # 2 AM daily UTC
    scheduler.add_job(locked_process_weekly_insights, CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="UTC"), id="process_weekly_insights", replace_existing=True) # 8 AM Monday UTC
    scheduler.add_job(locked_sync_patient_ltv_stats, CronTrigger(hour=1, minute=0, timezone="UTC"), id="sync_patient_ltv_stats", replace_existing=True) # 1 AM daily UTC
    scheduler.add_job(locked_process_daily_reports, CronTrigger(hour=9, minute=0, timezone="UTC"), id="process_daily_reports", replace_existing=True) # 9 AM daily UTC
    
    scheduler.start()
    log.info("APScheduler started with 13 background jobs (Reminders, RefreshViews, PurgeData, Followups, Insurance, Noshow, Recalls, Trials, DemoCleanup, DatabaseBackups, WeeklyInsights, PatientLTVStats, DailyReports).")
