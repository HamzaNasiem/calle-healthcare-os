import React, { useState, useEffect } from "react";
import {
  Bell,
  MessageSquare,
  Mail,
  Phone,
  Volume2,
  VolumeX,
  Smartphone,
  ShieldAlert,
  AlertCircle,
  CheckCircle2,
  CheckCircle,
  AlertTriangle,
  Clock,
  Sparkles,
  Calendar,
  Save,
  Loader2,
  RefreshCw,
  Send,
  ShieldCheck,
  Check,
  Zap,
  Info,
  ExternalLink,
  Layers
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { translations } from "../lib/translations";
import {
  playNotificationChime,
  getBrowserNotificationStatus,
  requestBrowserNotificationPermission,
  showBrowserNotification
} from "../lib/notifications";

import { DEFAULT_NOTIFICATIONS_CONFIG } from './notificationConstants.js';

const NotificationSettings = ({ clinicData, onClinicUpdate }) => {
  const { language } = useAuth();
  const t = translations[language] || translations.en;

  const [config, setConfig] = useState(DEFAULT_NOTIFICATIONS_CONFIG);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  // Audio testing state
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  // Browser notification permission state
  const [browserPerm, setBrowserPerm] = useState(getBrowserNotificationStatus());
  const [requestingPerm, setRequestingPerm] = useState(false);

  // Test Alert Dispatch state
  const [testAlertType, setTestAlertType] = useState("staff.alert");
  const [sendingTestAlert, setSendingTestAlert] = useState(false);
  const [testAlertResult, setTestAlertResult] = useState(null);

  const getClinicId = () => {
    if (clinicData?.id) return clinicData.id;
    const info = JSON.parse(localStorage.getItem("clinic-info") || sessionStorage.getItem("clinic-info") || "{}");
    return info.clinicId || "d3b07384-d113-46a6-a719-38cf89235d54";
  };

  useEffect(() => {
    // Initial sync from clinicData or API
    if (clinicData?.notifications_config) {
      setConfig({
        ...DEFAULT_NOTIFICATIONS_CONFIG,
        ...clinicData.notifications_config,
      });
    } else {
      fetchSettings();
    }
  }, [clinicData]);

  useEffect(() => {
    setBrowserPerm(getBrowserNotificationStatus());
  }, []);

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const cid = getClinicId();
      const res = await api.get(`/clinics/${cid}`);
      const data = res.data?.data || res.data;
      if (data?.notifications_config) {
        setConfig({
          ...DEFAULT_NOTIFICATIONS_CONFIG,
          ...data.notifications_config,
        });
      }
    } catch (err) {
      console.warn("[NotificationSettings] Failed to fetch clinic settings:", err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (key) => {
    setConfig((prev) => {
      const updated = {
        ...prev,
        [key]: !prev[key],
      };
      // If user toggles browser notifications ON, check and request permission if needed
      if (key === "browser_notifications_enabled" && !prev.browser_notifications_enabled) {
        handleRequestBrowserPermission();
      }
      return updated;
    });
  };

  const handleChange = (key, value) => {
    setConfig((prev) => ({
      ...prev,
      [key]: value,
    }));
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    setSaving(true);
    setMsg(null);

    // Basic email validation if filled
    if (config.staff_alert_email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(config.staff_alert_email.trim())) {
      setMsg({ type: "error", text: "Please enter a valid staff escalation email address." });
      setSaving(false);
      return;
    }

    try {
      const cid = getClinicId();
      const res = await api.put(`/clinics/${cid}`, {
        notifications_config: config,
      });
      const updatedData = res.data?.data || res.data;
      if (onClinicUpdate && updatedData) {
        onClinicUpdate(updatedData);
      }
      setMsg({ type: "success", text: "Notification preferences and alert routing saved successfully!" });
      setTimeout(() => setMsg(null), 4000);
    } catch (err) {
      setMsg({
        type: "error",
        text: err.response?.data?.detail || err.response?.data?.error || "Failed to save notification preferences.",
      });
    } finally {
      setSaving(false);
    }
  };

  const handlePlaySound = () => {
    setIsPlayingAudio(true);
    const success = playNotificationChime();
    setTimeout(() => {
      setIsPlayingAudio(false);
    }, 600);
  };

  const handleRequestBrowserPermission = async () => {
    setRequestingPerm(true);
    const res = await requestBrowserNotificationPermission();
    setBrowserPerm(res.permission);
    setRequestingPerm(false);

    if (res.permission === "granted") {
      setConfig((prev) => ({ ...prev, browser_notifications_enabled: true }));
      showBrowserNotification("Bytelytic OS — Notifications Active", {
        body: "Browser alerts are now enabled for urgent patient calls, bookings, and alerts.",
      });
      setMsg({ type: "success", text: "Browser notifications permission granted!" });
      setTimeout(() => setMsg(null), 3000);
    } else if (res.permission === "denied") {
      setConfig((prev) => ({ ...prev, browser_notifications_enabled: false }));
      setMsg({
        type: "error",
        text: "Browser notification permission was denied. Please allow notifications in your browser URL lock settings.",
      });
    }
  };

  const handleSendTestBrowserNotification = () => {
    if (browserPerm !== "granted") {
      handleRequestBrowserPermission();
      return;
    }
    showBrowserNotification("Bytelytic OS — Test Alert", {
      body: "✓ Notification delivery confirmed! In-app desktop push alerts are functioning properly.",
    });
    setMsg({ type: "success", text: "Test browser notification dispatched to your desktop." });
    setTimeout(() => setMsg(null), 3000);
  };

  const handleSendTestStaffAlert = async () => {
    setSendingTestAlert(true);
    setTestAlertResult(null);
    setMsg(null);

    const alertDetailsMap = {
      "staff.alert": {
        title: "Manual Staff Escalation Test",
        body: "Simulated test notification to verify staff escalation email and phone routing.",
        metadata: { source: "settings_test_panel", priority: "urgent" },
      },
      "sentiment.negative": {
        title: "Simulated Patient Distress Trigger",
        body: "Patient expressed strong frustration during intake: 'I have been waiting 45 minutes and need urgent attention.'",
        metadata: { sentiment: "frustrated", caller_name: "Sarah Jenkins", phone: "+1 (555) 234-5678" },
      },
      "call.missed": {
        title: "Simulated Missed Patient Call",
        body: "Inbound patient call after-hours was dropped: +1 (555) 987-6543 requested callback.",
        metadata: { call_duration_secs: 0, from_number: "+15559876543" },
      },
      "noshow.detected": {
        title: "Simulated Patient No-Show",
        body: "Patient John Doe (ID #10842) did not arrive for scheduled 10:00 AM Physical Therapy evaluation.",
        metadata: { appointment_type: "Physical Therapy Eval", scheduled_time: "10:00 AM" },
      },
    };

    const alertPayload = alertDetailsMap[testAlertType] || alertDetailsMap["staff.alert"];

    try {
      const res = await api.post("/notifications/test-alert", {
        alert_type: testAlertType,
        title: alertPayload.title,
        body: alertPayload.body,
        metadata: alertPayload.metadata,
      });

      setTestAlertResult({
        success: true,
        message: res.data?.message || "Test alert dispatched through staff routing channels.",
        routedToEmail: res.data?.routed_to_email || config.staff_alert_email || clinicData?.owner_email,
        routedToPhone: res.data?.routed_to_phone || config.staff_alert_phone || clinicData?.primary_doctor_phone,
      });

      setMsg({
        type: "success",
        text: `✓ Test alert dispatched successfully! Check ${config.staff_alert_email || clinicData?.owner_email || "your inbox"}.`,
      });
    } catch (err) {
      const errMsg = err.response?.data?.detail || err.response?.data?.error || err.message;
      setTestAlertResult({
        success: false,
        message: errMsg,
      });
      setMsg({
        type: "error",
        text: `Test alert failed: ${errMsg}`,
      });
    } finally {
      setSendingTestAlert(false);
    }
  };

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* ── Section Title & Primary Save Header ────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-surface-container pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-bold text-on-surface">Notification & Alert Preferences</h3>
          </div>
          <p className="text-xs text-on-surface-variant mt-1">
            Configure automated patient SMS communication, email digests, staff escalation thresholds, and in-app alerts.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={saving}
          className="btn-primary self-start sm:self-auto flex items-center gap-2 px-4 py-2 text-xs font-bold shadow-sm"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? "Saving Changes..." : "Save Preferences"}
        </button>
      </div>

      {/* ── Inline Feedback Toast ─────────────────────────────── */}
      {msg && (
        <div
          className={`px-4 py-3 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 transition-all animate-in fade-in ${
            msg.type === "success"
              ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]"
              : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
          }`}
        >
          <div className="flex items-center gap-2">
            {msg.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
            )}
            <span>{msg.text}</span>
          </div>
          <button
            onClick={() => setMsg(null)}
            className="text-xs opacity-70 hover:opacity-100 font-bold px-1.5 py-0.5"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── SECTION 1: Automated SMS Communications ──────────── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="w-4 h-4 text-primary" />
            <h4 className="text-sm font-bold text-on-surface uppercase tracking-wider">
              Automated Patient SMS Communications
            </h4>
          </div>
          <span className="text-[11px] font-semibold text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
            Patient Facing
          </span>
        </div>
        <p className="text-xs text-on-surface-variant">
          Control the automated SMS notifications sent to patients by your AI Receptionist and clinical workflows.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 pt-1">
          {[
            {
              key: "booking_confirmation_enabled",
              label: "Instant Booking Confirmation SMS",
              desc: "Dispatches SMS receipt with appointment date, time, and service details immediately upon booking.",
              icon: CheckCircle2,
              badge: "Immediate",
            },
            {
              key: "cancellation_confirmation_enabled",
              label: "Cancellation & Reschedule SMS",
              desc: "Sends confirmation receipt when a patient cancels or reschedules their appointment.",
              icon: Calendar,
              badge: "Immediate",
            },
            {
              key: "reminders_enabled",
              label: "24-Hour Appointment Reminders",
              desc: "Sends SMS 24 hours prior to scheduled visits with interactive confirm/cancel reply options.",
              icon: Clock,
              badge: "24h Prior",
            },
            {
              key: "followup_enabled",
              label: "Post-Visit Follow-Up SMS",
              desc: "Sends caring check-in SMS 48 hours after completed visits to assess patient recovery.",
              icon: Sparkles,
              badge: "48h Post-Visit",
            },
            {
              key: "recall_enabled",
              label: "Patient Recall Outreach",
              desc: "Outbound AI outreach for inactive patients due for follow-ups at 30, 60, and 90 day intervals.",
              icon: RefreshCw,
              badge: "Interval Cadence",
            },
            {
              key: "insurance_enabled",
              label: "Insurance Verification SMS",
              desc: "Sends SMS 48 hours before appointments requesting patient insurance confirmation.",
              icon: ShieldCheck,
              badge: "48h Prior",
            },
          ].map((item) => {
            const Icon = item.icon;
            const isEnabled = config[item.key] !== false;
            return (
              <div
                key={item.key}
                className={`p-4 rounded-xl border transition-all flex items-start justify-between gap-3 ${
                  isEnabled
                    ? "bg-surface-container/60 border-primary/20 shadow-xs"
                    : "bg-surface-container/20 border-surface-container opacity-80"
                }`}
              >
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  <div
                    className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${
                      isEnabled ? "bg-primary/10 text-primary" : "bg-surface-container text-on-surface-variant"
                    }`}
                  >
                    <Icon className="w-4.5 h-4.5" />
                  </div>
                  <div className="flex-1 min-w-0 pr-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-xs font-bold text-on-surface">{item.label}</p>
                      <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                        {item.badge}
                      </span>
                    </div>
                    <p className="text-[11px] text-on-surface-variant leading-relaxed mt-1">{item.desc}</p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleToggle(item.key)}
                  className={`relative w-11 h-6 rounded-full transition-colors focus:outline-none flex-shrink-0 self-center ${
                    isEnabled ? "bg-[#7dbd42]" : "bg-surface-container-highest"
                  }`}
                  aria-label={`Toggle ${item.label}`}
                >
                  <span
                    className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                      isEnabled ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── SECTION 2: Email Notification Preferences ─────────── */}
      <div className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Mail className="w-4 h-4 text-primary" />
            <h4 className="text-sm font-bold text-on-surface uppercase tracking-wider">
              Email Notification Preferences
            </h4>
          </div>
          <span className="text-[11px] font-semibold text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
            Clinic Management
          </span>
        </div>
        <p className="text-xs text-on-surface-variant">
          Configure automated email summaries, quota tracking alerts, and clinic health digests.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5 pt-1">
          {[
            {
              key: "email_daily_report_enabled",
              label: "Daily Morning Digest",
              desc: "Recap email sent every morning summarizing calls, booked appointments, and revenue.",
              icon: Mail,
            },
            {
              key: "email_quota_alerts_enabled",
              label: "Call & SMS Quota Alerts",
              desc: "Automated alerts when your practice reaches 80% and 100% of monthly plan quota.",
              icon: Zap,
            },
            {
              key: "email_staff_alerts_enabled",
              label: "Urgent Escalation Emails",
              desc: "Instant email dispatches when negative sentiment, dropped calls, or no-shows occur.",
              icon: ShieldAlert,
            },
          ].map((item) => {
            const Icon = item.icon;
            const isEnabled = config[item.key] !== false;
            return (
              <div
                key={item.key}
                className={`p-4 rounded-xl border transition-all flex flex-col justify-between gap-3 ${
                  isEnabled
                    ? "bg-surface-container/60 border-primary/20"
                    : "bg-surface-container/20 border-surface-container opacity-80"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      isEnabled ? "bg-primary/10 text-primary" : "bg-surface-container text-on-surface-variant"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <button
                    type="button"
                    onClick={() => handleToggle(item.key)}
                    className={`relative w-10 h-5 rounded-full transition-colors focus:outline-none flex-shrink-0 ${
                      isEnabled ? "bg-[#7dbd42]" : "bg-surface-container-highest"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                        isEnabled ? "translate-x-5" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
                <div>
                  <p className="text-xs font-bold text-on-surface">{item.label}</p>
                  <p className="text-[11px] text-on-surface-variant leading-relaxed mt-1">{item.desc}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── SECTION 3: Staff Alert Routing & Escalation Triggers ── */}
      <div className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-primary" />
            <h4 className="text-sm font-bold text-on-surface uppercase tracking-wider">
              Staff Alert Routing & Escalation Triggers
            </h4>
          </div>
          <span className="text-[11px] font-semibold text-[#b71c1c] bg-[#ffebee] px-2.5 py-1 rounded-full border border-[#ffcdd2]">
            High Priority
          </span>
        </div>
        <p className="text-xs text-on-surface-variant">
          Define routing destinations and automated escalation triggers for urgent clinical situations.
        </p>

        {/* Staff Routing Contact Inputs */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 rounded-xl bg-surface-container/50 border border-surface-container">
          <div>
            <label className="overline mb-1.5 flex items-center gap-1.5 text-on-surface">
              <Mail className="w-3.5 h-3.5 text-primary" />
              <span>Staff Escalation Email Address</span>
            </label>
            <div className="flex items-center input-field bg-surface-container-highest gap-2 px-3 py-2 rounded-lg">
              <input
                type="email"
                value={config.staff_alert_email || ""}
                onChange={(e) => handleChange("staff_alert_email", e.target.value)}
                placeholder={clinicData?.owner_email || "e.g. staff@yourclinic.com"}
                className="flex-1 bg-transparent border-none outline-none text-xs text-on-surface"
              />
            </div>
            <p className="text-[10px] text-on-surface-variant mt-1">
              Defaults to clinic owner email ({clinicData?.owner_email || "primary email"}) if left empty.
            </p>
          </div>

          <div>
            <label className="overline mb-1.5 flex items-center gap-1.5 text-on-surface">
              <Smartphone className="w-3.5 h-3.5 text-primary" />
              <span>Staff Urgent SMS Phone Number</span>
            </label>
            <div className="flex items-center input-field bg-surface-container-highest gap-2 px-3 py-2 rounded-lg">
              <input
                type="tel"
                value={config.staff_alert_phone || ""}
                onChange={(e) => handleChange("staff_alert_phone", e.target.value)}
                placeholder={clinicData?.primary_doctor_phone || "+1 (555) 000-0000"}
                className="flex-1 bg-transparent border-none outline-none text-xs text-on-surface font-mono"
              />
            </div>
            <p className="text-[10px] text-on-surface-variant mt-1">
              Receives instant SMS dispatch when critical escalation triggers occur.
            </p>
          </div>
        </div>

        {/* Escalation Trigger Thresholds */}
        <div className="space-y-3 pt-1">
          <p className="text-xs font-bold text-on-surface">Escalation Trigger Thresholds</p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            {[
              {
                key: "alert_on_negative_sentiment",
                label: "Patient Distress / Negative Sentiment",
                desc: "Triggers urgent alert when AI receptionist detects patient frustration, anger, or urgent concerns.",
                icon: AlertCircle,
                badge: "AI Sentiment Analysis",
              },
              {
                key: "alert_on_missed_calls",
                label: "Missed & Dropped Calls",
                desc: "Immediately alerts staff when a patient call is missed, dropped, or unable to be answered.",
                icon: Phone,
                badge: "Telephony Trigger",
              },
              {
                key: "alert_on_noshow",
                label: "Appointment No-Shows",
                desc: "Dispatches escalation alert when an appointment is marked as a no-show.",
                icon: Clock,
                badge: "Scheduling Trigger",
              },
            ].map((item) => {
              const Icon = item.icon;
              const isEnabled = config[item.key] !== false;
              return (
                <div
                  key={item.key}
                  className={`p-4 rounded-xl border transition-all flex flex-col justify-between gap-3 ${
                    isEnabled
                      ? "bg-surface-container/60 border-primary/20 shadow-xs"
                      : "bg-surface-container/20 border-surface-container opacity-80"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div
                      className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                        isEnabled ? "bg-[#fce4ec] text-[#b71c1c]" : "bg-surface-container text-on-surface-variant"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <button
                      type="button"
                      onClick={() => handleToggle(item.key)}
                      className={`relative w-10 h-5 rounded-full transition-colors focus:outline-none flex-shrink-0 ${
                        isEnabled ? "bg-[#7dbd42]" : "bg-surface-container-highest"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                          isEnabled ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </div>
                  <div>
                    <span className="text-[9px] font-semibold uppercase tracking-wider text-on-surface-variant/80">
                      {item.badge}
                    </span>
                    <p className="text-xs font-bold text-on-surface mt-0.5">{item.label}</p>
                    <p className="text-[11px] text-on-surface-variant leading-relaxed mt-1">{item.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── SECTION 4: In-App Sound Alerts & Desktop Push ─────── */}
      <div className="space-y-4 pt-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Volume2 className="w-4 h-4 text-primary" />
            <h4 className="text-sm font-bold text-on-surface uppercase tracking-wider">
              Sound Alerts & Browser Desktop Notifications
            </h4>
          </div>
          <span className="text-[11px] font-semibold text-on-surface-variant bg-surface-container px-2.5 py-1 rounded-full">
            In-App Live Alerts
          </span>
        </div>
        <p className="text-xs text-on-surface-variant">
          Audio cues and native browser notifications ensure your reception desk never misses an appointment or call.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {/* Sound Alerts Card */}
          <div className="p-4 rounded-xl border border-surface-container bg-surface-container/50 space-y-3.5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
                  {config.sound_alerts_enabled ? (
                    <Volume2 className="w-4.5 h-4.5" />
                  ) : (
                    <VolumeX className="w-4.5 h-4.5 text-on-surface-variant" />
                  )}
                </div>
                <div>
                  <p className="text-xs font-bold text-on-surface">Audible Chime Alert</p>
                  <p className="text-[11px] text-on-surface-variant mt-0.5">
                    Plays harmonic audio cue when new calls, appointments, or messages arrive.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleToggle("sound_alerts_enabled")}
                className={`relative w-11 h-6 rounded-full transition-colors focus:outline-none flex-shrink-0 ${
                  config.sound_alerts_enabled !== false ? "bg-[#7dbd42]" : "bg-surface-container-highest"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                    config.sound_alerts_enabled !== false ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            <div className="pt-1 flex items-center justify-between border-t border-surface-container">
              <span className="text-[11px] text-on-surface-variant">Web Audio API Synthesis</span>
              <button
                type="button"
                onClick={handlePlaySound}
                disabled={isPlayingAudio}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-surface-container-high hover:bg-surface-container-highest text-on-surface transition-all active:scale-95"
              >
                <Volume2 className={`w-3.5 h-3.5 ${isPlayingAudio ? "animate-bounce text-primary" : ""}`} />
                <span>{isPlayingAudio ? "Playing Chime..." : "Test Audio Chime"}</span>
              </button>
            </div>
          </div>

          {/* Browser Push Notifications Card */}
          <div className="p-4 rounded-xl border border-surface-container bg-surface-container/50 space-y-3.5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-lg bg-primary/10 text-primary flex items-center justify-center flex-shrink-0">
                  <Bell className="w-4.5 h-4.5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-bold text-on-surface">Desktop Browser Notifications</p>
                    {browserPerm === "granted" && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 bg-[#edf7e0] text-[#396a00] rounded">
                        Granted
                      </span>
                    )}
                    {browserPerm === "denied" && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 bg-[#fce4ec] text-[#b71c1c] rounded">
                        Blocked
                      </span>
                    )}
                    {browserPerm === "default" && (
                      <span className="text-[10px] font-bold px-1.5 py-0.2 bg-[#fff8e1] text-[#f57f17] rounded">
                        Action Required
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-on-surface-variant mt-0.5">
                    Receive desktop popups even if the dashboard tab is in the background.
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={() => handleToggle("browser_notifications_enabled")}
                className={`relative w-11 h-6 rounded-full transition-colors focus:outline-none flex-shrink-0 ${
                  config.browser_notifications_enabled ? "bg-[#7dbd42]" : "bg-surface-container-highest"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-sm transition-transform duration-200 ease-in-out ${
                    config.browser_notifications_enabled ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            <div className="pt-1 flex items-center justify-between border-t border-surface-container">
              {browserPerm === "granted" ? (
                <span className="text-[11px] text-[#396a00] flex items-center gap-1 font-medium">
                  <Check className="w-3.5 h-3.5" /> Browser push active
                </span>
              ) : (
                <span className="text-[11px] text-on-surface-variant">Permission needed</span>
              )}

              {browserPerm !== "granted" ? (
                <button
                  type="button"
                  onClick={handleRequestBrowserPermission}
                  disabled={requestingPerm}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-primary text-white hover:opacity-90 transition-all active:scale-95 shadow-xs"
                >
                  {requestingPerm ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Bell className="w-3.5 h-3.5" />
                  )}
                  <span>Grant Permission</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleSendTestBrowserNotification}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold bg-surface-container-high hover:bg-surface-container-highest text-on-surface transition-all active:scale-95"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Send Test Popup</span>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── SECTION 5: Staff Alert Live Simulation & Verification ── */}
      <div className="p-5 rounded-xl border border-primary/20 bg-primary/5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary text-white flex items-center justify-center flex-shrink-0">
              <Zap className="w-4 h-4" />
            </div>
            <div>
              <h4 className="text-xs font-bold text-on-surface uppercase tracking-wider">
                Live Staff Escalation Router Verification
              </h4>
              <p className="text-[11px] text-on-surface-variant mt-0.5">
                Simulate a real critical trigger to verify end-to-end delivery to your staff email and SMS number.
              </p>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-3 items-center">
          <select
            value={testAlertType}
            onChange={(e) => setTestAlertType(e.target.value)}
            className="input-field text-xs bg-surface-container-highest text-on-surface py-2.5 px-3 rounded-lg border-none outline-none font-medium cursor-pointer"
          >
            <option value="staff.alert">🚨 Test General Urgent Staff Escalation</option>
            <option value="sentiment.negative">😡 Test Negative Patient Sentiment / Concern Trigger</option>
            <option value="call.missed">📞 Test Dropped / Missed Call Trigger</option>
            <option value="noshow.detected">⏰ Test Patient Appointment No-Show Trigger</option>
          </select>

          <button
            type="button"
            onClick={handleSendTestStaffAlert}
            disabled={sendingTestAlert}
            className="px-4 py-2.5 rounded-lg text-xs font-bold bg-[#1a3a2e] text-white hover:bg-[#142e24] transition-all flex items-center justify-center gap-2 shadow-xs active:scale-95"
          >
            {sendingTestAlert ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
            <span>{sendingTestAlert ? "Dispatching Alert..." : "Dispatch Verification Alert"}</span>
          </button>
        </div>

        {testAlertResult && (
          <div
            className={`p-3 rounded-lg text-xs flex items-start gap-2 animate-in fade-in ${
              testAlertResult.success
                ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]"
                : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
            }`}
          >
            {testAlertResult.success ? (
              <CheckCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1">
              <p className="font-bold">{testAlertResult.message}</p>
              {testAlertResult.success && (
                <p className="text-[11px] opacity-90 mt-0.5">
                  Routed to: Email (<code>{testAlertResult.routedToEmail}</code>) & Phone (
                  <code>{testAlertResult.routedToPhone || "None configured"}</code>)
                </p>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Bottom Save Action Bar ────────────────────────────── */}
      <div className="flex items-center justify-between pt-4 border-t border-surface-container">
        <p className="text-[11px] text-on-surface-variant">
          All settings are saved directly to PostgreSQL and take effect immediately.
        </p>

        <button
          type="button"
          onClick={handleSave}
          disabled={saving}
          className="btn-primary flex items-center gap-2 px-5 py-2.5 text-xs font-bold shadow-sm"
        >
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? "Saving Changes..." : "Save Notification Preferences"}
        </button>
      </div>
    </div>
  );
};

export default NotificationSettings;
