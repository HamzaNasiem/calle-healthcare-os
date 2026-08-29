from sqlalchemy.future import select

from src.core.logger import log
from src.db.engine import async_session_maker
from src.models.outbox import OutboxEvent


async def process_outbox_events():
    """
    Background worker that picks up PENDING outbox events and executes them.
    Guarantees at-least-once delivery for integrations (Retell, Telnyx, EHR, WebSocket).
    """
    try:
        async with async_session_maker() as session:
            # 1. Fetch PENDING events, limiting to 50 at a time to prevent memory exhaustion
            stmt = select(OutboxEvent).where(
                OutboxEvent.status == "PENDING"
            ).order_by(OutboxEvent.created_at.asc()).limit(50)
            
            # Using with_for_update(skip_locked=True) ensures that if multiple workers are running,
            # they don't pick up the same events.
            stmt = stmt.with_for_update(skip_locked=True)
            
            result = await session.execute(stmt)
            events = result.scalars().all()
            
            if not events:
                return
                
            for event in events:
                event.status = "PROCESSING"
                
            await session.commit()
            
            # 2. Process events
            from src.services.sms_service import sms_service
            from src.services.ws_service import ws_service

            for event in events:
                try:
                    if event.event_type == "SEND_SMS":
                        payload = event.payload or {}
                        sms_type = payload.get("type", "general")
                        to_phone = payload.get("to_number") or payload.get("phone")

                        if sms_type == "appointment_confirmation":
                            time_str = payload.get("time_str")
                            if not time_str:
                                apt_date = payload.get("apt_date")
                                apt_time = payload.get("apt_time")
                                if apt_date and apt_time:
                                    time_str = f"{apt_date} at {apt_time}"
                                else:
                                    time_str = apt_time or apt_date or "your scheduled appointment"

                            res = await sms_service.send_booking_confirmation(
                                phone=to_phone,
                                time_str=time_str,
                                provider_name=payload.get("provider_name"),
                                tenant_id=event.tenant_id,
                                patient_name=payload.get("patient_name"),
                                confirmation_code=payload.get("confirmation_code"),
                                appointment_id=payload.get("appointment_id"),
                                patient_id=payload.get("patient_id")
                            )
                            if not res.get("success", False):
                                raise Exception(f"send_booking_confirmation failed: {res.get('error', 'Unknown error')}")

                        elif sms_type in ["live_link", "live_link_sms", "live_sms_link"]:
                            res = await sms_service.send_live_link_sms(
                                phone=to_phone,
                                link_type=payload.get("link_type", "intake_form"),
                                url=payload.get("url"),
                                tenant_id=event.tenant_id,
                                patient_id=payload.get("patient_id")
                            )
                            if not res.get("success", False):
                                raise Exception(f"send_live_link_sms failed: {res.get('error', 'Unknown error')}")

                        elif sms_type in ["reminder_24h", "fallback_reminder"]:
                            msg = payload.get("message")
                            if not msg:
                                time_val = payload.get("apt_time", "tomorrow")
                                pat_name = payload.get("patient_name", "Patient")
                                prov_name = payload.get("provider_name", "our clinic")
                                msg = f"Reminder for {pat_name}: You have an appointment at {time_val} with {prov_name}. Reply YES to confirm or CANCEL."

                            res = await sms_service.send(
                                clinic_id=event.tenant_id,
                                to=to_phone,
                                body=msg,
                                sms_type=sms_type,
                                appointment_id=payload.get("appointment_id"),
                                patient_id=payload.get("patient_id")
                            )
                            if not res.get("success", False):
                                raise Exception(f"send reminder failed: {res.get('error', 'Unknown error')}")

                        elif sms_type == "waitlist_slot_opened":
                            day = payload.get("day", "an upcoming date")
                            time_val = payload.get("time", "a slot")
                            service = payload.get("service_type", "appointment")
                            msg = f"Good news! A {service} appointment slot opened on {day} at {time_val}. Reply YES to claim it!"

                            res = await sms_service.send(
                                clinic_id=event.tenant_id,
                                to=to_phone,
                                body=msg,
                                sms_type="waitlist",
                                patient_id=payload.get("patient_id")
                            )
                            if not res.get("success", False):
                                raise Exception(f"send waitlist failed: {res.get('error', 'Unknown error')}")

                        else:
                            body_text = payload.get("text") or payload.get("body") or payload.get("message") or ""
                            if to_phone and body_text:
                                res = await sms_service.send(
                                    clinic_id=event.tenant_id,
                                    to=to_phone,
                                    body=body_text,
                                    sms_type=sms_type or "general",
                                    appointment_id=payload.get("appointment_id"),
                                    patient_id=payload.get("patient_id")
                                )
                                if not res.get("success", False):
                                    raise Exception(f"send text failed: {res.get('error', 'Unknown error')}")
                    
                    elif event.event_type == "WS_BROADCAST":
                        payload = event.payload or {}
                        await ws_service.broadcast(
                            tenant_id=str(event.tenant_id),
                            event_type=payload.get("ws_event_type"),
                            payload=payload.get("data", {})
                        )
                    
                    event.status = "COMPLETED"
                except Exception as e:
                    log.error(f"[Outbox] Failed to process event {event.id}: {str(e)}")
                    event.last_error = str(e)[:490]
                    event.retries += 1
                    
                    if event.retries >= 5:
                        log.critical(f"[Outbox] Event {event.id} failed 5 times. Moving to DEAD_LETTER queue.")
                        event.status = "DEAD_LETTER"
                    else:
                        event.status = "PENDING"
            
            # 3. Save status updates
            async with async_session_maker() as update_session:
                for event in events:
                    # Re-attach and merge
                    await update_session.merge(event)
                await update_session.commit()
                
    except Exception as e:
        log.error(f"[Outbox] Worker encountered an error: {str(e)}")
