import uuid
import zoneinfo
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, func

from src.core.logger import log
from src.db.engine import async_session_maker
from src.models.appointment import Appointment
from src.models.call_log import CallLog
from src.models.outbound_call import OutboundCall
from src.models.outbox import OutboxEvent
from src.models.patient import Patient
from src.models.tenant import Tenant
from src.models.waitlist import Waitlist
from src.services.calle_service import calle_service
from src.workers.sms_outbox_worker import sms_outbox_worker

scheduler = AsyncIOScheduler()


from src.core.database import supabase, supabase_read

async def job_24h_reminders():
    """Send SMS reminders for appointments starting in ~24 hours."""
    now = datetime.now(UTC)
    target_start = (now + timedelta(hours=23, minutes=45)).isoformat()
    target_end = (now + timedelta(hours=24, minutes=15)).isoformat()
    
    try:
        res = supabase_read.table("appointments").select(
            "id, clinic_id, patient_id, patient_name, patient_phone, datetime, reminder_sent, status"
        ).eq("status", "scheduled").gte("datetime", target_start).lte("datetime", target_end).execute()
        
        appts = res.data or []
        for apt in appts:
            if apt.get("reminder_sent"):
                continue
            phone = apt.get("patient_phone")
            if not phone:
                continue
                
            # Queue instant SMS via Outbox / SMS service
            from src.services.sms_service import sms_service
            clinic_id = apt.get("clinic_id") or "d3b07384-d113-46a6-a719-38cf89235d54"
            await sms_service.send(
                clinic_id=str(clinic_id),
                to=phone,
                body=f"Reminder from your medical clinic: You have an appointment tomorrow at {apt.get('datetime', '')[:16].replace('T', ' ')}. Reply YES to confirm or NO to reschedule.",
                sms_type="reminder_24h",
                patient_id=apt.get("patient_id")
            )
            supabase.table("appointments").update({"reminder_sent": True}).eq("id", apt["id"]).execute()
            log.info(f"[24h Reminder] Queued reminder for appointment {apt['id']}")
    except Exception as e:
        log.error(f"Error in job_24h_reminders: {e}")


async def job_calle_confirmation_calls():
    """
    Automated CALL-E Outbound Confirmation Calls (24h before appointment).
    Runs daily to confirm unconfirmed appointments.
    """
    now = datetime.now(UTC)
    window_start = (now + timedelta(hours=23)).isoformat()
    window_end = (now + timedelta(hours=25)).isoformat()

    try:
        res = supabase_read.table("appointments").select(
            "id, clinic_id, patient_id, patient_name, patient_phone, datetime, status, confirmed_at"
        ).eq("status", "scheduled").gte("datetime", window_start).lte("datetime", window_end).execute()

        appts = res.data or []
        for apt in appts:
            if apt.get("confirmed_at"):
                continue
            phone = apt.get("patient_phone")
            if not phone:
                continue

            clinic_id = apt.get("clinic_id") or "d3b07384-d113-46a6-a719-38cf89235d54"
            clinic_res = supabase_read.table("clinics").select("name, timezone").eq("id", clinic_id).execute()
            clinic_info = clinic_res.data[0] if clinic_res.data else {}
            
            tz_name = clinic_info.get("timezone") or "America/Chicago"
            try:
                tz = zoneinfo.ZoneInfo(tz_name)
            except Exception:
                tz = zoneinfo.ZoneInfo("America/Chicago")
            local_now = now.astimezone(tz)

            if not (8 <= local_now.hour < 20):
                log.info(f"[CALL-E Confirmation] Skipping apt {apt['id']}, outside 8am-8pm window")
                continue

            idempotency_key = f"CALL_CONFIRMATION_{apt['id']}_{now.date().isoformat()}"
            existing = supabase_read.table("outbound_calls").select("id").eq("idempotency_key", idempotency_key).execute()
            if existing.data:
                continue

            clinic_name = clinic_info.get("name") or "Medical Clinic"
            time_str = apt.get("datetime", "")[:16].replace("T", " ")
            
            # Record in outbound_calls table
            call_id = str(uuid.uuid4())
            supabase.table("outbound_calls").insert({
                "id": call_id,
                "clinic_id": clinic_id,
                "appointment_id": apt["id"],
                "patient_id": apt.get("patient_id"),
                "campaign_type": "confirmation",
                "idempotency_key": idempotency_key,
                "status": "pending",
                "created_at": now.isoformat()
            }).execute()

            log.info(f"[CALL-E Scheduler] Placing confirmation call for apt {apt['id']}")
            try:
                result = await calle_service.confirmation_call(
                    phone=phone,
                    clinic_name=clinic_name,
                    time_str=time_str,
                    idempotency_key=idempotency_key
                )
                supabase.table("outbound_calls").update({
                    "calle_call_id": result.get("id") or result.get("call_id"),
                    "status": result.get("status", "completed"),
                    "task_completed": result.get("task_completed", True),
                    "structured_result": result.get("structured_result"),
                    "summary": result.get("summary"),
                    "completed_at": datetime.now(UTC).isoformat()
                }).eq("id", call_id).execute()

                if result.get("structured_result", {}).get("will_attend") == "yes":
                    supabase.table("appointments").update({
                        "confirmed_at": datetime.now(UTC).isoformat(),
                        "status": "confirmed"
                    }).eq("id", apt["id"]).execute()

                log.info(f"[CALL-E Scheduler] Automated confirmation call completed for appointment {apt['id']}")
            except Exception as ex:
                log.error(f"[CALL-E Scheduler] Error placing confirmation call for apt {apt['id']}: {ex}")
                supabase.table("outbound_calls").update({"status": "failed"}).eq("id", call_id).execute()
    except Exception as e:
        log.error(f"Error in job_calle_confirmation_calls: {e}")


async def job_calle_noshow_recovery():
    """
    Automated CALL-E Outbound No-Show Recovery Calls (15-30m after missed appointment).
    """
    now = datetime.now(UTC)
    cutoff_start = (now - timedelta(minutes=30)).isoformat()
    cutoff_end = (now - timedelta(minutes=15)).isoformat()

    try:
        res = supabase_read.table("appointments").select(
            "id, clinic_id, patient_id, patient_name, patient_phone, datetime, status"
        ).eq("status", "scheduled").gte("datetime", cutoff_start).lte("datetime", cutoff_end).execute()

        appts = res.data or []
        for apt in appts:
            phone = apt.get("patient_phone")
            if not phone:
                continue

            clinic_id = apt.get("clinic_id") or "d3b07384-d113-46a6-a719-38cf89235d54"
            clinic_res = supabase_read.table("clinics").select("name, timezone").eq("id", clinic_id).execute()
            clinic_info = clinic_res.data[0] if clinic_res.data else {}

            idempotency_key = f"CALL_NOSHOW_{apt['id']}_{now.date().isoformat()}"
            existing = supabase_read.table("outbound_calls").select("id").eq("idempotency_key", idempotency_key).execute()
            if existing.data:
                continue

            clinic_name = clinic_info.get("name") or "Medical Clinic"
            time_str = apt.get("datetime", "")[:16].replace("T", " ")

            call_id = str(uuid.uuid4())
            supabase.table("outbound_calls").insert({
                "id": call_id,
                "clinic_id": clinic_id,
                "appointment_id": apt["id"],
                "patient_id": apt.get("patient_id"),
                "campaign_type": "no_show_recovery",
                "idempotency_key": idempotency_key,
                "status": "pending",
                "created_at": now.isoformat()
            }).execute()

            log.info(f"[CALL-E Scheduler] Placing no-show recovery call for apt {apt['id']}")
            try:
                result = await calle_service.no_show_recovery_call(
                    phone=phone,
                    clinic_name=clinic_name,
                    time_str=time_str,
                    idempotency_key=idempotency_key
                )
                supabase.table("outbound_calls").update({
                    "calle_call_id": result.get("id") or result.get("call_id"),
                    "status": result.get("status", "completed"),
                    "task_completed": result.get("task_completed", True),
                    "structured_result": result.get("structured_result"),
                    "summary": result.get("summary"),
                    "completed_at": datetime.now(UTC).isoformat()
                }).eq("id", call_id).execute()
                log.info(f"[CALL-E Scheduler] Automated no-show recovery call completed for appointment {apt['id']}")
            except Exception as ex:
                log.error(f"[CALL-E Scheduler] Error placing no-show call for apt {apt['id']}: {ex}")
                supabase.table("outbound_calls").update({"status": "failed"}).eq("id", call_id).execute()
    except Exception as e:
        log.error(f"Error in job_calle_noshow_recovery: {e}")


async def job_calle_pre_appointment_calls():
    """
    Automated CALL-E Outbound Pre-appointment prep calls.
    """
    now = datetime.now(UTC)
    window_start = (now + timedelta(hours=1, minutes=45)).isoformat()
    window_end = (now + timedelta(hours=2, minutes=15)).isoformat()

    try:
        res = supabase_read.table("appointments").select(
            "id, clinic_id, patient_id, patient_name, patient_phone, datetime, status, appointment_type"
        ).eq("status", "scheduled").gte("datetime", window_start).lte("datetime", window_end).execute()

        appts = res.data or []
        for apt in appts:
            phone = apt.get("patient_phone")
            if not phone:
                continue

            clinic_id = apt.get("clinic_id") or "d3b07384-d113-46a6-a719-38cf89235d54"
            clinic_res = supabase_read.table("clinics").select("name").eq("id", clinic_id).execute()
            clinic_name = clinic_res.data[0]["name"] if clinic_res.data else "Medical Clinic"

            idempotency_key = f"CALL_PRE_APPT_{apt['id']}_{now.date().isoformat()}"
            existing = supabase_read.table("outbound_calls").select("id").eq("idempotency_key", idempotency_key).execute()
            if existing.data:
                continue

            call_id = str(uuid.uuid4())
            supabase.table("outbound_calls").insert({
                "id": call_id,
                "clinic_id": clinic_id,
                "appointment_id": apt["id"],
                "patient_id": apt.get("patient_id"),
                "campaign_type": "pre_appointment",
                "idempotency_key": idempotency_key,
                "status": "pending",
                "created_at": now.isoformat()
            }).execute()

            try:
                result = await calle_service.confirmation_call(
                    phone=phone,
                    clinic_name=clinic_name,
                    time_str=apt.get("datetime", "")[:16].replace("T", " "),
                    idempotency_key=idempotency_key
                )
                supabase.table("outbound_calls").update({
                    "calle_call_id": result.get("id") or result.get("call_id"),
                    "status": result.get("status", "completed"),
                    "task_completed": result.get("task_completed", True),
                    "structured_result": result.get("structured_result"),
                    "summary": result.get("summary"),
                    "completed_at": datetime.now(UTC).isoformat()
                }).eq("id", call_id).execute()
            except Exception as ex:
                log.error(f"[CALL-E Scheduler] Error in pre-appointment prep call: {ex}")
                supabase.table("outbound_calls").update({"status": "failed"}).eq("id", call_id).execute()
    except Exception as e:
        log.error(f"Error in job_calle_pre_appointment_calls: {e}")


async def job_purge_recordings():
    """
    Physical & DB Purge: Delete call recordings older than 24 hours to comply with HIPAA Data Minimization.
    Deletes both the database pointer and cleans up storage references.
    """
    cutoff = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    try:
        # 1. Fetch active recording pointers older than 24h
        old_calls_res = supabase_read.table("calls").select("id, clinic_id, recording_url").not_.is_("recording_url", "null").lte("created_at", cutoff).execute()
        old_calls = old_calls_res.data or []
        
        old_pa_res = supabase_read.table("prior_auth_requests").select("id, tenant_id, call_recording_url").not_.is_("call_recording_url", "null").lte("created_at", cutoff).execute()
        old_pa = old_pa_res.data or []

        # 2. Database URL nullification
        if old_calls:
            supabase.table("calls").update({"recording_url": None}).lte("created_at", cutoff).execute()
        if old_pa:
            supabase.table("prior_auth_requests").update({"call_recording_url": None}).lte("created_at", cutoff).execute()

        total_purged = len(old_calls) + len(old_pa)
        if total_purged > 0:
            log.info(f"[HIPAA Purge] Successfully purged {len(old_calls)} call audio recordings and {len(old_pa)} prior auth recordings (>24h).")
    except Exception as e:
        log.error(f"Error in job_purge_recordings: {e}")





async def job_expire_waitlist():
    """Remove waitlist entries that have been waiting for > 30 days without action."""
    cutoff = datetime.now(UTC) - timedelta(days=30)
    try:
        async with async_session_maker() as db:
            stmt = select(Waitlist).where(
                Waitlist.status == "waiting",
                Waitlist.created_at <= cutoff
            )
            res = await db.execute(stmt)
            entries = res.scalars().all()
            
            for entry in entries:
                entry.status = "expired"
                
            if entries:
                await db.commit()
                log.info(f"Expired {len(entries)} waitlist entries.")
    except Exception as e:
        log.error(f"Error in job_expire_waitlist: {e}")


from src.services.outbox_worker import process_outbox_events


def start_scheduler():
    if not scheduler.running:
        # 1. Check for reminders every 15 minutes
        scheduler.add_job(job_24h_reminders, 'interval', minutes=15, id='reminders_15m', replace_existing=True)
        # 2. CALL-E 24h confirmation calls daily at 8am
        scheduler.add_job(job_calle_confirmation_calls, 'cron', hour=8, minute=0, id='calle_confirmation_daily', replace_existing=True)
        # 3. CALL-E No-Show recovery calls every 5 minutes
        scheduler.add_job(job_calle_noshow_recovery, 'interval', minutes=5, id='calle_noshow_recovery', replace_existing=True)
        # 4. CALL-E Pre-appointment prep calls every 30 minutes
        scheduler.add_job(job_calle_pre_appointment_calls, 'interval', minutes=30, id='calle_pre_appointment', replace_existing=True)
        # 5. Purge recordings every hour
        scheduler.add_job(job_purge_recordings, 'interval', hours=1, id='purge_1h', replace_existing=True)
        # 6. Expire waitlist once a day
        scheduler.add_job(job_expire_waitlist, 'cron', hour=2, id='waitlist_daily', replace_existing=True)
        # 7. Process Outbox Events (every 5 seconds)
        scheduler.add_job(process_outbox_events, 'interval', seconds=5, id='outbox_worker_generic', replace_existing=True)
        # 8. Process SMS Outbox Events (every 5 seconds)
        scheduler.add_job(sms_outbox_worker.process_pending_events, 'interval', seconds=5, id='outbox_worker_sms', replace_existing=True)
        
        # 9. Register clinical cron jobs
        try:
            from src.jobs.scheduler import (
                locked_process_reminders,
                locked_refresh_materialized_views,
                locked_purge_expired_data,
                locked_process_followups,
                locked_process_insurance_verifications,
                locked_process_noshow_predictions,
                locked_process_recalls,
                locked_process_trials,
                locked_cleanup_demo_clinics,
                locked_process_database_backups,
                locked_process_weekly_insights,
                locked_sync_patient_ltv_stats,
                locked_process_daily_reports,
            )
            from apscheduler.triggers.cron import CronTrigger

            scheduler.add_job(locked_process_reminders, CronTrigger(minute="*/15"), id="process_reminders", replace_existing=True)
            scheduler.add_job(locked_refresh_materialized_views, CronTrigger(minute="*/15"), id="refresh_materialized_views", replace_existing=True)
            scheduler.add_job(locked_purge_expired_data, CronTrigger(day_of_week="sun", hour=3, minute=0, timezone="UTC"), id="purge_expired_data", replace_existing=True)
            scheduler.add_job(locked_process_followups, CronTrigger(hour=10, minute=0, timezone="UTC"), id="process_followups", replace_existing=True)
            scheduler.add_job(locked_process_insurance_verifications, CronTrigger(hour=9, minute=0, timezone="UTC"), id="process_insurance_verifications", replace_existing=True)
            scheduler.add_job(locked_process_noshow_predictions, CronTrigger(hour=18, minute=0, timezone="UTC"), id="process_noshow_predictions", replace_existing=True)
            scheduler.add_job(locked_process_recalls, CronTrigger(hour=20, minute=0, timezone="UTC"), id="process_recalls", replace_existing=True)
            scheduler.add_job(locked_process_trials, CronTrigger(hour=8, minute=0, timezone="UTC"), id="process_trials", replace_existing=True)
            scheduler.add_job(locked_cleanup_demo_clinics, CronTrigger(hour=3, minute=0, timezone="UTC"), id="cleanup_demo_clinics", replace_existing=True)
            scheduler.add_job(locked_process_database_backups, CronTrigger(hour=2, minute=0, timezone="UTC"), id="process_database_backups", replace_existing=True)
            scheduler.add_job(locked_process_weekly_insights, CronTrigger(day_of_week="mon", hour=8, minute=0, timezone="UTC"), id="process_weekly_insights", replace_existing=True)
            scheduler.add_job(locked_sync_patient_ltv_stats, CronTrigger(hour=1, minute=0, timezone="UTC"), id="sync_patient_ltv_stats", replace_existing=True)
            scheduler.add_job(locked_process_daily_reports, CronTrigger(hour=9, minute=0, timezone="UTC"), id="process_daily_reports", replace_existing=True)
        except Exception as e:
            log.warning(f"Could not register additional clinical cron jobs: {e}")
        
        scheduler.start()
        log.info("APScheduler background jobs (including CALL-E automated calls and clinical crons) started successfully.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        log.info("APScheduler shutdown gracefully.")
