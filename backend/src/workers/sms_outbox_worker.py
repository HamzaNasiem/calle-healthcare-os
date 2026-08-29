import asyncio
import traceback

from sqlalchemy import select

from src.core.logger import log
from src.db.engine import async_session_maker
from src.models.outbox import OutboxEvent
from src.services.sms_service import sms_service


class SMSOutboxWorker:
    def __init__(self, poll_interval_seconds: int = 5):
        self.poll_interval = poll_interval_seconds
        self._running = False
        self._task = None

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self.poll_loop())
            log.info("SMS Outbox Worker started.")

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            log.info("SMS Outbox Worker stopped.")

    async def poll_loop(self):
        while self._running:
            try:
                await self.process_pending_events()
            except Exception as e:
                log.error(f"Error in SMS Outbox Worker poll loop: {e}")
                log.error(traceback.format_exc())
            await asyncio.sleep(self.poll_interval)

    async def process_pending_events(self):
        try:
            async with async_session_maker() as db:
                # 1. Fetch pending SMS events and lock them
                stmt = select(OutboxEvent).where(
                    OutboxEvent.event_type == "SEND_SMS",
                    OutboxEvent.status == "PENDING"
                ).order_by(OutboxEvent.created_at.asc()).with_for_update(skip_locked=True).limit(50)
                
                result = await db.execute(stmt)
                events = result.scalars().all()
                
                if not events:
                    return

                for event in events:
                    try:
                        payload = event.payload
                        sms_type = payload.get("type", "unknown")
                        to_number = payload.get("to_number")
                        patient_id = payload.get("patient_id")
                        appointment_id = payload.get("appointment_id")

                        if not to_number:
                            raise ValueError("Missing 'to_number' in payload")
                            
                        # Generate Message Body
                        if sms_type == "appointment_confirmation":
                            message_body = await sms_service.generate_confirmation_message(db, event.tenant_id, payload)
                        elif sms_type == "reminder_24h":
                            message_body = await sms_service.generate_reminder_message(db, event.tenant_id, payload)
                        elif sms_type == "live_sms_link":
                            message_body = await sms_service.generate_live_link_message(db, event.tenant_id, payload)
                        elif sms_type == "waitlist_slot_opened":
                            message_body = await sms_service.generate_waitlist_message(db, event.tenant_id, payload)
                        else:
                            message_body = payload.get("text", "")
                            if not message_body:
                                raise ValueError(f"Unknown sms_type '{sms_type}' and no fallback text provided.")

                        # Send and Log SMS
                        await sms_service.send_sms(
                            db=db,
                            tenant_id=event.tenant_id,
                            to_number=to_number,
                            message_body=message_body,
                            sms_type=sms_type,
                            patient_id=patient_id,
                            appointment_id=appointment_id
                        )
                        
                        event.status = "COMPLETED"
                        
                    except Exception as e:
                        event.status = "FAILED"
                        event.last_error = str(e)[:490]
                        log.error(f"Failed to process OutboxEvent {event.id}: {e}")
                        
                await db.commit()
        except Exception as e:
            log.warning(f"SMS Outbox Worker cycle skipped: {e}")

sms_outbox_worker = SMSOutboxWorker()
