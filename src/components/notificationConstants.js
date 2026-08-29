// Notification settings default configuration constants
// Extracted to a separate file to comply with Vite React Fast Refresh rules

export const DEFAULT_NOTIFICATIONS_CONFIG = {
  booking_confirmation_enabled: true,
  cancellation_confirmation_enabled: true,
  reminders_enabled: true,
  recall_enabled: true,
  followup_enabled: true,
  insurance_enabled: true,
  email_daily_report_enabled: true,
  email_quota_alerts_enabled: true,
  email_staff_alerts_enabled: true,
  staff_alert_email: "",
  staff_alert_phone: "",
  alert_on_negative_sentiment: true,
  alert_on_missed_calls: true,
  alert_on_noshow: true,
  sound_alerts_enabled: true,
  browser_notifications_enabled: false,
};
