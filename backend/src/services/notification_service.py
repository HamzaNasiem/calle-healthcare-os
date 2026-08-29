"""
Notification Service
====================
Creates structured notifications in the `notifications` table.
Supabase Realtime picks up these inserts and pushes them to subscribed frontend clients instantly.

Notification Types:
  - appointment.booked       → AI ne appointment book ki
  - appointment.cancelled    → Appointment cancel hui
  - call.completed           → AI call khatam hua
  - call.missed              → Missed call
  - sms.received             → Patient ne SMS bheja
  - noshow.detected          → No-show mark hua
  - recall.sent              → Recall SMS bheja gaya
  - system.error             → Background job fail hua
"""

import asyncio
from typing import Optional, Literal
from ..core.database import supabase
from ..core.logger import log

NotificationType = Literal[
    "appointment.booked",
    "appointment.cancelled",
    "appointment.updated",
    "call.completed",
    "call.missed",
    "sms.received",
    "noshow.detected",
    "recall.sent",
    "system.error",
    "system.info",
    "staff.alert",
    "sentiment.negative",
    "test.alert",
]


class NotificationService:
    async def create(
        self,
        clinic_id: str,
        notification_type: NotificationType,
        title: str,
        body: str,
        metadata: Optional[dict] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ) -> None:
        """
        Insert a notification row — Supabase Realtime delivers it to the frontend instantly.
        Always fire-and-forget (asyncio.create_task) so it never blocks the caller.
        """
        asyncio.create_task(
            self._insert(
                clinic_id=clinic_id,
                notification_type=notification_type,
                title=title,
                body=body,
                metadata=metadata or {},
                resource_type=resource_type,
                resource_id=resource_id,
            )
        )

    async def _insert(
        self,
        clinic_id: str,
        notification_type: str,
        title: str,
        body: str,
        metadata: dict,
        resource_type: Optional[str],
        resource_id: Optional[str],
    ) -> dict:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("notifications").insert({
                    "clinic_id": clinic_id,
                    "type": notification_type,
                    "title": title,
                    "body": body,
                    "metadata": metadata,
                    "resource_type": resource_type,
                    "resource_id": resource_id,
                    "is_read": False,
                }).execute()
            )
        except Exception as e:
            log.warning(f"[NotificationService] Failed to insert notification: {e}")

        # Check and trigger staff alert routing (Email and/or SMS)
        routing_res = {}
        try:
            routing_res = await self._check_staff_alert_routing(
                clinic_id=clinic_id,
                notification_type=notification_type,
                title=title,
                body=body,
                metadata=metadata,
            )
        except Exception as alert_err:
            log.warning(f"[NotificationService] Staff alert routing warning: {alert_err}")

        return routing_res or {}

    async def _check_staff_alert_routing(
        self,
        clinic_id: str,
        notification_type: str,
        title: str,
        body: str,
        metadata: dict,
    ) -> dict:
        """
        Check clinic's notification preferences and route urgent staff alerts
        via email and SMS based on alert thresholds (missed calls, sentiment, no-shows).
        """
        result = {
            "routed": False,
            "routed_to_email": None,
            "routed_to_phone": None,
            "reason": None,
        }
        try:
            res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("clinics").select("name, owner_email, primary_doctor_phone, notifications_config, business_hours").eq("id", clinic_id).single().execute()
            )
            if not res or not res.data:
                return result

            clinic = res.data
            notif_config = clinic.get("notifications_config")
            if not isinstance(notif_config, dict):
                hours = clinic.get("business_hours") or {}
                notif_config = hours.get("_notifications_config") if isinstance(hours, dict) else {}
            if not isinstance(notif_config, dict):
                notif_config = {}

            clinic_name = clinic.get("name", "Your Clinic")
            staff_email = notif_config.get("staff_alert_email") or clinic.get("owner_email")
            staff_phone = notif_config.get("staff_alert_phone") or clinic.get("primary_doctor_phone")

            sentiment = str(metadata.get("sentiment", "")).lower()
            is_negative_sentiment = (
                sentiment in ["negative", "concern", "frustrated", "angry", "upset"]
                or notification_type in ["sentiment.negative", "patient.sentiment_negative"]
            )
            is_missed_call = notification_type == "call.missed"
            is_noshow = notification_type == "noshow.detected"
            is_staff_alert = notification_type in ["staff.alert", "test.alert", "urgent.escalation"]

            should_alert = False
            alert_reason = ""

            if is_negative_sentiment and notif_config.get("alert_on_negative_sentiment", True):
                should_alert = True
                alert_reason = "Negative Patient Sentiment / Concern"
            elif is_missed_call and notif_config.get("alert_on_missed_calls", True):
                should_alert = True
                alert_reason = "Missed / Dropped Patient Call"
            elif is_noshow and notif_config.get("alert_on_noshow", True):
                should_alert = True
                alert_reason = "Patient No-Show Detected"
            elif is_staff_alert:
                should_alert = True
                alert_reason = "Urgent Staff Escalation"

            if not should_alert:
                return result

            result["routed"] = True
            result["reason"] = alert_reason

            # 1. Dispatch Staff Escalation Email
            if staff_email and notif_config.get("email_staff_alerts_enabled", True):
                from .email_service import email_service
                await email_service.send_staff_urgent_alert(
                    recipient_email=staff_email,
                    clinic_name=clinic_name,
                    alert_title=f"{alert_reason}: {title}",
                    alert_body=body,
                    metadata=metadata
                )
                result["routed_to_email"] = staff_email

            # 2. Dispatch Staff SMS Alert if staff_alert_phone is configured
            if staff_phone:
                from .sms_service import sms_service
                sms_body = f"URGENT [{clinic_name}]: {alert_reason}. {title} — {body}"
                if len(sms_body) > 155:
                    sms_body = sms_body[:152] + "..."
                await sms_service.send(
                    clinic_id=clinic_id,
                    to=staff_phone,
                    body=sms_body,
                    sms_type="staff_alert"
                )
                result["routed_to_phone"] = staff_phone

            return result
        except Exception as e:
            log.warning(f"[NotificationService] Failed to evaluate staff alert routing: {e}")
            return result

    async def trigger_test_alert(
        self,
        clinic_id: str,
        alert_type: str,
        title: str,
        body: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Directly triggers a test alert and waits for routing to complete."""
        meta = metadata or {}
        return await self._insert(
            clinic_id=clinic_id,
            notification_type=alert_type,
            title=title,
            body=body,
            metadata=meta,
            resource_type="system",
            resource_id="test",
        )

    async def mark_read(self, clinic_id: str, notification_id: str) -> bool:
        try:
            res = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("notifications")
                    .update({"is_read": True})
                    .eq("id", notification_id)
                    .eq("clinic_id", clinic_id)
                    .execute()
            )
            return bool(res.data)
        except Exception as e:
            log.warning(f"[NotificationService] Failed to mark notification read: {e}")
            return False

    async def mark_all_read(self, clinic_id: str) -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: supabase.table("notifications")
                    .update({"is_read": True})
                    .eq("clinic_id", clinic_id)
                    .eq("is_read", False)
                    .execute()
            )
        except Exception as e:
            log.warning(f"[NotificationService] Failed to mark all read: {e}")


notification_service = NotificationService()
