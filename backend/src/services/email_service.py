import anyio
from typing import Dict, Any, Optional
from ..core.config import settings
from .connectors.resend_email_connector import ResendEmailConnector

class EmailService:
    def __init__(self):
        self.connector = ResendEmailConnector()

    async def _send_email_async(self, from_email: str, to_emails: list, subject: str, html_body: str) -> str:
        try:
            return await self.connector.send_email(from_email, to_emails, subject, html_body)
        except Exception as e:
            err_msg = str(e)
            if "not verified" in err_msg.lower() or "domain is not verified" in err_msg.lower():
                fallback_from = "onboarding@resend.dev"
                fallback_to = ["ziaee.pk@gmail.com"]
                print(f"[EmailService] WARNING: Domain not verified. Falling back from '{from_email}' to '{fallback_from}' and redirecting to '{fallback_to}'")
                try:
                    orig_recipient = to_emails[0] if to_emails else "unknown"
                    return await self.connector.send_email(fallback_from, fallback_to, f"[DEV-REDIRECT to {orig_recipient}] {subject}", html_body)
                except Exception as inner_e:
                    print(f"[EmailService] Fallback sending also failed: {inner_e}")
                    raise inner_e
            raise e

    async def send_welcome_email(self, clinic: dict, temporary_password: str) -> Optional[Dict[str, Any]]:
        dashboard_url = settings.DASHBOARD_URL or "http://localhost:5173"
        
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <h1 style="color: #1a3a2e;">Welcome to Bytelytic, {clinic.get('name')}!</h1>
            <p>Your AI receptionist is fully configured and ready to take calls right now.</p>
            
            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="margin-top: 0; color: #396a00;">Your Dedicated Phone Number:</h2>
                <p style="font-size: 24px; font-weight: bold; margin: 0;">{clinic.get('phone_number')}</p>
            </div>
            
            <h3>Dashboard Login Details</h3>
            <p><strong>URL:</strong> <a href="{dashboard_url}">{dashboard_url}</a></p>
            <p><strong>Email:</strong> {clinic.get('owner_email')}</p>
            <p><strong>Password:</strong> You can log in using the password you just created.</p>
            
            <h3>Next Steps</h3>
            <ol>
                <li>Log in to your dashboard.</li>
                <li>Call your new phone number above and test your AI receptionist.</li>
                <li>Connect your Google Calendar in the Settings page.</li>
            </ol>
            
            <p>If you have any questions, reply directly to this email!</p>
            <br/>
            <p>Cheers,<br/>The Bytelytic Team</p>
        </div>
        """

        try:
            email_id = await self._send_email_async(
                from_email="Bytelytic OS <onboarding@bytelytic.com>",
                to_emails=[clinic["owner_email"]],
                subject="Welcome to Bytelytic OS - Your AI Receptionist is Live!",
                html_body=html_content
            )
            print(f"[EmailService] Welcome email sent to {clinic['owner_email']}")
            return {"id": email_id}
        except Exception as e:
            print(f"[EmailService] Failed to send welcome email: {str(e)}")
            return None

    async def send_appointment_confirmation_email(
        self,
        patient_email: str,
        patient_name: str,
        appointment_date: str,   # e.g. "Monday, August 18, 2026"
        appointment_time: str,   # e.g. "10:30 AM"
        doctor_name: str,
        service_type: str,
        confirmation_code: str,
        clinic_name: str,
        clinic_phone: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Send appointment confirmation email to patient after booking."""
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
            <div style="background: linear-gradient(135deg, #1a3a2e, #396a00); padding: 30px; border-radius: 12px 12px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 24px;">✅ Appointment Confirmed</h1>
                <p style="color: #a8d8a8; margin: 8px 0 0 0;">Your appointment has been successfully scheduled.</p>
            </div>
            
            <div style="background: #f9fafb; padding: 30px; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none;">
                <h2 style="color: #1a3a2e; margin-top: 0;">Hi {patient_name},</h2>
                <p>Your appointment at <strong>{clinic_name}</strong> has been confirmed. Here are the details:</p>
                
                <div style="background: white; border: 2px solid #396a00; border-radius: 8px; padding: 20px; margin: 20px 0;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 8px 0; color: #666; width: 40%;">📅 Date</td><td style="padding: 8px 0; font-weight: bold;">{appointment_date}</td></tr>
                        <tr><td style="padding: 8px 0; color: #666;">🕐 Time</td><td style="padding: 8px 0; font-weight: bold;">{appointment_time}</td></tr>
                        <tr><td style="padding: 8px 0; color: #666;">👨⚕️ Doctor</td><td style="padding: 8px 0; font-weight: bold;">{doctor_name}</td></tr>
                        <tr><td style="padding: 8px 0; color: #666;">🏥 Service</td><td style="padding: 8px 0; font-weight: bold;">{service_type}</td></tr>
                        <tr style="border-top: 1px solid #e5e7eb;"><td style="padding: 12px 0 4px; color: #666;">🔖 Confirmation Code</td><td style="padding: 12px 0 4px; font-weight: bold; font-size: 18px; color: #396a00; letter-spacing: 2px;">{confirmation_code}</td></tr>
                    </table>
                </div>
                
                <p style="font-size: 14px; color: #666;">Please save your confirmation code <strong>{confirmation_code}</strong> for your records. You may need it to reschedule or cancel your appointment.</p>
                
                {'<p>📞 Need to reschedule? Call us at <strong>' + clinic_phone + '</strong></p>' if clinic_phone else ''}
                
                <p style="margin-top: 24px;">See you soon!<br/><strong>The {clinic_name} Team</strong></p>
            </div>
        </div>
        """
        try:
            email_id = await self._send_email_async(
                from_email=f"{clinic_name} <appointments@bytelytic.com>",
                to_emails=[patient_email],
                subject=f"✅ Appointment Confirmed — {appointment_date} at {appointment_time}",
                html_body=html_content
            )
            return {"email_id": email_id, "status": "sent"}
        except Exception as e:
            print(f"[EmailService] Appointment confirmation email failed: {e}")
            return {"email_id": None, "status": "failed", "error": str(e)}

    async def send_alert_email(self, message: str) -> None:
        """Send critical alert email to Bytelytic admin."""
        try:
            await self._send_email_async(
                from_email="Bytelytic System <alerts@bytelytic.com>",
                to_emails=["ziaee.pk@gmail.com"],
                subject="⚠️ Bytelytic OS — System Alert",
                html_body=f"<div style='font-family:Arial;max-width:600px;margin:0 auto;'><h2 style='color:#dc2626;'>System Alert</h2><p>{message}</p><p style='color:#6b7280;font-size:12px;'>Bytelytic OS — Automated Alert</p></div>"
            )
            print(f"[EmailService] Alert email sent")
        except Exception as e:
            print(f"[EmailService] Failed to send alert email: {e}")

    async def send_staff_urgent_alert(self, recipient_email: str, clinic_name: str, alert_title: str, alert_body: str, metadata: Optional[dict] = None) -> None:
        """Send urgent staff escalation alert email directly to designated clinic staff email."""
        if not recipient_email:
            return
        try:
            dashboard_url = settings.DASHBOARD_URL or "https://dashboard-two-jade-54.vercel.app"
            meta_rows = ""
            if metadata and isinstance(metadata, dict):
                for k, v in metadata.items():
                    if v and k not in ["raw", "transcript", "recording_url"]:
                        key_label = k.replace("_", " ").capitalize()
                        meta_rows += f"<tr><td style='padding:6px 0;color:#6b7280;font-size:13px;'>{key_label}</td><td style='padding:6px 0;font-weight:600;font-size:13px;text-align:right;'>{v}</td></tr>"
            
            meta_section = f"""
            <div style='background:#f9fafb;border-radius:6px;padding:12px 16px;margin:16px 0;'>
                <table style='width:100%;border-collapse:collapse;'>
                    {meta_rows}
                </table>
            </div>
            """ if meta_rows else ""

            html_body = f"""
            <div style='font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1f2937;line-height:1.5;'>
                <div style='background:#fef2f2;border-left:4px solid #ef4444;padding:16px;border-radius:4px;margin-bottom:20px;'>
                    <h2 style='color:#b91c1c;margin:0 0 8px 0;font-size:18px;'>🚨 {alert_title}</h2>
                    <p style='margin:0;color:#374151;font-size:14px;'>{alert_body}</p>
                </div>
                {meta_section}
                <div style='margin-top:24px;'>
                    <a href='{dashboard_url}' style='display:inline-block;background:#b91c1c;color:#ffffff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;'>Open Clinic Dashboard</a>
                </div>
                <p style='color:#9ca3af;font-size:11px;margin-top:30px;'>Bytelytic OS — Staff Alert Escalation Router</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Staff Alerts <alerts@bytelytic.com>",
                to_emails=[recipient_email],
                subject=f"⚠️ [{clinic_name}] {alert_title}",
                html_body=html_body
            )
            print(f"[EmailService] Staff urgent alert email sent to {recipient_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send staff urgent alert email: {e}")

    async def send_daily_report(self, clinic: dict, stats: dict) -> None:
        """Send daily summary report to clinic owner."""
        clinic_name = clinic.get("name", "Your Clinic")
        owner_email = clinic.get("owner_email")
        if not owner_email:
            return
            
        # Check if daily report emails are enabled in clinic preferences
        notif_config = clinic.get("notifications_config") or {}
        if not isinstance(notif_config, dict):
            hours = clinic.get("business_hours") or {}
            notif_config = hours.get("_notifications_config") if isinstance(hours, dict) else {}
        if isinstance(notif_config, dict) and notif_config.get("email_daily_report_enabled") is False:
            print(f"[EmailService] Daily report email disabled in notifications_config for {clinic.get('id')}. Skipping.")
            return

        dashboard_url = settings.DASHBOARD_URL or "https://dashboard-two-jade-54.vercel.app"
        calls = stats.get("totalCalls", 0)
        appts = stats.get("totalAppointments", 0)
        revenue = stats.get("revenueRecoveredDollars", 0)
        try:
            html_body = f"""
            <div style='font-family:Arial;max-width:600px;margin:0 auto;color:#333;'>
                <h1 style='color:#1a3a2e;'>Good morning!</h1>
                <p>Here's yesterday's summary for <strong>{clinic_name}</strong>:</p>
                <div style='background:#f3f4f6;padding:20px;border-radius:8px;margin:20px 0;'>
                    <table style='width:100%;border-collapse:collapse;'>
                        <tr><td style='padding:8px 0;'><strong>Total Calls</strong></td><td style='text-align:right;'>{calls}</td></tr>
                        <tr><td style='padding:8px 0;'><strong>Appointments Booked</strong></td><td style='text-align:right;'>{appts}</td></tr>
                        <tr><td style='padding:8px 0;'><strong>Revenue Recovered</strong></td><td style='text-align:right;color:#396a00;'><strong>${revenue}</strong></td></tr>
                    </table>
                </div>
                <a href='{dashboard_url}' style='display:inline-block;background:#396a00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;'>View Full Dashboard</a>
                <p style='color:#9ca3af;font-size:12px;margin-top:20px;'>Bytelytic OS — AI Receptionist</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Daily <reports@bytelytic.com>",
                to_emails=[owner_email],
                subject=f"📊 Daily Report — {clinic_name}",
                html_body=html_body
            )
            print(f"[EmailService] Daily report sent to {owner_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send daily report: {e}")

    async def send_quota_warning_email(self, owner_email: str, clinic_id: str, calls_count: int, calls_limit: int) -> None:
        """Send 80% soft quota capacity limit warning email directly to clinic owner."""
        try:
            from ..core.database import supabase
            res = supabase.table("clinics").select("notifications_config, business_hours").eq("id", clinic_id).single().execute()
            if res.data:
                c_conf = res.data.get("notifications_config")
                if not isinstance(c_conf, dict):
                    b_hrs = res.data.get("business_hours") or {}
                    c_conf = b_hrs.get("_notifications_config") if isinstance(b_hrs, dict) else {}
                if isinstance(c_conf, dict) and c_conf.get("email_quota_alerts_enabled") is False:
                    print(f"[EmailService] Quota alert email disabled in notifications_config for {clinic_id}. Skipping.")
                    return
        except Exception:
            pass
        try:
            dashboard_url = settings.DASHBOARD_URL or "http://localhost:5173"
            html_body = f"""
            <div style='font-family:Arial;max-width:600px;margin:0 auto;color:#333;'>
                <h2 style='color:#d97706;'>Quota warning: 80% limit reached</h2>
                <p>Your Bytelytic AI receptionist has currently answered <strong>{calls_count}</strong> out of your plan's monthly allocation of <strong>{calls_limit}</strong> calls.</p>
                <p>To ensure your patients can continue to book appointments and receive automatic notifications with zero interruptions, we recommend upgrading your subscription tier.</p>
                <a href='{dashboard_url}/settings?tab=billing' style='display:inline-block;background:#396a00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:15px;'>Manage Subscription Plan</a>
                <p style='color:#9ca3af;font-size:12px;margin-top:30px;'>Bytelytic OS — Billing Notifications</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Billing <billing@bytelytic.com>",
                to_emails=[owner_email],
                subject="⚠️ Call Quota Alert: 80% Capacity Reached",
                html_body=html_body
            )
            print(f"[EmailService] Quota 80% warning email sent successfully to {owner_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send quota warning email: {e}")

    async def send_quota_exhausted_email(self, owner_email: str, clinic_id: str, calls_count: int, calls_limit: int) -> None:
        """Send 100% hard quota exhaustion deactivation alert directly to clinic owner."""
        try:
            dashboard_url = settings.DASHBOARD_URL or "http://localhost:5173"
            html_body = f"""
            <div style='font-family:Arial;max-width:600px;margin:0 auto;color:#333;'>
                <h2 style='color:#dc2626;'>AI receptionist paused: 100% capacity reached</h2>
                <p>Your Bytelytic AI receptionist has answered <strong>{calls_count}</strong> out of your monthly plan limit of <strong>{calls_limit}</strong> calls. Your monthly quota is now fully exhausted.</p>
                <p style='color:#dc2626;font-weight:bold;'>Patient call answering and scheduling features have been temporarily paused to prevent additional charges.</p>
                <p>To restore automatic operations immediately, please upgrade your subscription plan below.</p>
                <a href='{dashboard_url}/settings?tab=billing' style='display:inline-block;background:#396a00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:15px;'>Reactivate & Upgrade Now</a>
                <p style='color:#9ca3af;font-size:12px;margin-top:30px;'>Bytelytic OS — Billing Notifications</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Billing <billing@bytelytic.com>",
                to_emails=[owner_email],
                subject="🚨 AI Receptionist Paused: Call Quota Exhausted",
                html_body=html_body
            )
            print(f"[EmailService] Quota 100% deactivation email sent successfully to {owner_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send quota deactivation email: {e}")

    async def send_sms_quota_warning_email(self, owner_email: str, clinic_id: str, sms_count: int, sms_limit: int) -> None:
        """Send 80% soft SMS quota capacity limit warning email directly to clinic owner."""
        try:
            dashboard_url = settings.DASHBOARD_URL or "http://localhost:5173"
            html_body = f"""
            <div style='font-family:Arial;max-width:600px;margin:0 auto;color:#333;'>
                <h2 style='color:#d97706;'>SMS Quota Warning: 80% limit reached</h2>
                <p>Your Bytelytic clinic system has currently dispatched <strong>{sms_count}</strong> out of your plan's monthly allocation of <strong>{sms_limit}</strong> SMS notifications.</p>
                <p>To ensure your patients can continue to receive automatic appointment reminders, follow-ups, and verification texts with zero interruptions, we recommend upgrading your subscription plan.</p>
                <a href='{dashboard_url}/settings?tab=billing' style='display:inline-block;background:#396a00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:15px;'>Manage Subscription Plan</a>
                <p style='color:#9ca3af;font-size:12px;margin-top:30px;'>Bytelytic OS — Billing Notifications</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Billing <billing@bytelytic.com>",
                to_emails=[owner_email],
                subject="⚠️ SMS Quota Alert: 80% Capacity Reached",
                html_body=html_body
            )
            print(f"[EmailService] SMS 80% warning email sent successfully to {owner_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send SMS quota warning email: {e}")

    async def send_sms_quota_exhausted_email(self, owner_email: str, clinic_id: str, sms_count: int, sms_limit: int) -> None:
        """Send 100% hard SMS quota exhaustion deactivation alert directly to clinic owner."""
        try:
            dashboard_url = settings.DASHBOARD_URL or "http://localhost:5173"
            html_body = f"""
            <div style='font-family:Arial;max-width:600px;margin:0 auto;color:#333;'>
                <h2 style='color:#dc2626;'>AI SMS notifications paused: 100% capacity reached</h2>
                <p>Your Bytelytic clinic system has dispatched <strong>{sms_count}</strong> out of your plan's monthly allocation of <strong>{sms_limit}</strong> SMS notifications. Your monthly SMS quota is now fully exhausted.</p>
                <p style='color:#dc2626;font-weight:bold;'>Patient SMS reminders, confirmation texts, and follow-ups have been temporarily paused to prevent additional charges.</p>
                <p>To restore automatic operations immediately, please upgrade your subscription plan below.</p>
                <a href='{dashboard_url}/settings?tab=billing' style='display:inline-block;background:#396a00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:15px;'>Reactivate & Upgrade Now</a>
                <p style='color:#9ca3af;font-size:12px;margin-top:30px;'>Bytelytic OS — Billing Notifications</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Billing <billing@bytelytic.com>",
                to_emails=[owner_email],
                subject="🚨 AI Notifications Paused: SMS Quota Exhausted",
                html_body=html_body
            )
            print(f"[EmailService] SMS 100% deactivation email sent successfully to {owner_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send SMS quota deactivation email: {e}")

    async def send_trial_reminder_email(self, owner_email: str, clinic_id: str, days_left: int) -> None:
        """Send a reminder email when trial is close to expiration."""
        try:
            dashboard_url = settings.DASHBOARD_URL or "http://localhost:5173"
            subject = f"Your trial ends in {days_left} days — add card to continue"
            html_body = f"""
            <div style='font-family:Arial;max-width:600px;margin:0 auto;color:#333;'>
                <h2 style='color:#1a3a2e;'>Your trial ends in {days_left} days</h2>
                <p>We hope you're enjoying your AI receptionist and automated clinic workflow.</p>
                <p>To ensure your patients experience zero interruptions when your trial ends, please add a payment method and select a subscription plan now. All your configurations and data will be seamlessly preserved.</p>
                <a href='{dashboard_url}/settings?tab=billing' style='display:inline-block;background:#396a00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:15px;'>Add Card to Continue</a>
                <p style='color:#9ca3af;font-size:12px;margin-top:30px;'>Bytelytic OS — Billing Notifications</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Billing <billing@bytelytic.com>",
                to_emails=[owner_email],
                subject=subject,
                html_body=html_body
            )
            print(f"[EmailService] Trial reminder email sent to {owner_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send trial reminder email: {e}")

    async def send_trial_ended_email(self, owner_email: str, clinic_id: str) -> None:
        """Send a notification that the trial has expired and the clinic is suspended."""
        try:
            dashboard_url = settings.DASHBOARD_URL or "http://localhost:5173"
            html_body = f"""
            <div style='font-family:Arial;max-width:600px;margin:0 auto;color:#333;'>
                <h2 style='color:#dc2626;'>Your 14-day free trial has expired</h2>
                <p>Your AI receptionist and automated patient notifications have been temporarily paused.</p>
                <p>Your clinic settings, patient data, and AI configurations are safely preserved. To reactivate your clinic and continue using Bytelytic OS, simply choose a plan that fits your volume.</p>
                <a href='{dashboard_url}/settings?tab=billing' style='display:inline-block;background:#396a00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;margin-top:15px;'>Upgrade & Reactivate</a>
                <p style='color:#9ca3af;font-size:12px;margin-top:30px;'>Bytelytic OS — Billing Notifications</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Billing <billing@bytelytic.com>",
                to_emails=[owner_email],
                subject="🚨 Your Bytelytic Trial Has Ended",
                html_body=html_body
            )
            print(f"[EmailService] Trial ended email sent to {owner_email}")
        except Exception as e:
            print(f"[EmailService] Failed to send trial ended email: {e}")

    async def send_staff_invite_email(self, email: str, clinic_name: str, temp_password: str, role: str) -> None:
        """Send invitation email to a new staff member."""
        try:
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
                <h2 style="color: #1a3a2e;">Welcome to Bytelytic OS</h2>
                <p>You have been invited by <b>{clinic_name}</b> to join their workspace as a <b>{role}</b>.</p>
                <p>Your temporary password is: <b>{temp_password}</b></p>
                <p>Please log in and you will have access to the dashboard.</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic OS <onboarding@bytelytic.com>",
                to_emails=[email],
                subject=f"You've been invited to join {clinic_name}",
                html_body=html_body
            )
            print(f"[EmailService] Staff invite email sent successfully to {email}")
        except Exception as e:
            print(f"[EmailService] Failed to send staff invite email: {e}")
            
    async def send_demo_welcome_email(self, email: str, name: str, clinic_name: str, temp_password: str) -> None:
        """Send a welcome email to the user with their demo credentials."""
        try:
            dashboard_url = settings.DASHBOARD_URL or "https://dashboard-two-jade-54.vercel.app"
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; color: #333;">
                <h1 style="color: #1a3a2e;">Your Sandbox Demo Clinic is Ready!</h1>
                <p>Welcome, {name}. We have successfully auto-provisioned your sandbox demo clinic.</p>
                
                <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #7FCD4D;">
                    <h3 style="margin-top: 0; color: #1a3a2e;">Demo Dashboard Login Details</h3>
                    <p><strong>Login URL:</strong> <a href="{dashboard_url}/login">{dashboard_url}/login</a></p>
                    <p><strong>Email:</strong> {email}</p>
                    <p><strong>Temporary Password:</strong> <code style="background: #e5e7eb; padding: 2px 6px; border-radius: 4px;">{temp_password}</code></p>
                </div>
                
                <p>Your demo environment is pre-loaded with realistic patient lists, past appointments, and receptionist call logs, allowing you to evaluate all Bytelytic features instantly.</p>
                <p><em>Note: This sandbox demo clinic is active for 7 days and will be auto-deleted afterward.</em></p>
                <br/>
                <p>Cheers,<br/>The Bytelytic Team</p>
            </div>
            """
            await self._send_email_async(
                from_email="Bytelytic Demo <onboarding@bytelytic.com>",
                to_emails=[email],
                subject="Your demo clinic is ready to try",
                html_body=html_body
            )
            print(f"[EmailService] Demo welcome email sent to {email}")
        except Exception as e:
            print(f"[EmailService] Failed to send demo welcome email: {e}")

email_service = EmailService()
