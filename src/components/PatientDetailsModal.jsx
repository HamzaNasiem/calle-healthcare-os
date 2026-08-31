import React, { useState, useEffect } from "react";
import {
  X,
  Calendar,
  Phone,
  MessageSquare,
  FileCheck2,
  ShieldCheck,
  ShieldAlert,
  Clock,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Copy,
  Check,
  Sparkles,
  Edit,
  ExternalLink,
  ChevronRight,
  Eye,
  EyeOff,
  User,
  HeartPulse,
  Send,
  Loader2
} from "lucide-react";
import api from "../lib/api";
import { format, parseISO, differenceInYears } from "date-fns";

const initials = (name) =>
  (name || "?")
    .split(" ")
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

const AVATAR_COLORS = [
  { bg: "#d4e8c1", text: "#2a5200" },
  { bg: "#c8d9e8", text: "#004d78" },
  { bg: "#e8d4c1", text: "#7a3500" },
  { bg: "#d4c1e8", text: "#4a1a70" },
  { bg: "#fce4ec", text: "#880e4f" },
];
const avatarStyle = (name) =>
  AVATAR_COLORS[(name?.charCodeAt(0) || 0) % AVATAR_COLORS.length];

export const getRecallTag = (patient) => {
  if (patient.recall_opted_out) {
    return { label: "Opted Out", bg: "bg-surface-container", text: "text-on-surface-variant", border: "border-outline-variant/30" };
  }
  
  const status = patient.recall_status;
  if (status === "overdue_60d") {
    return { label: "Overdue 60d+", bg: "bg-red-500/10 text-red-700 dark:text-red-400", border: "border-red-500/20", icon: AlertCircle };
  }
  if (status === "due_for_recall") {
    return { label: "Due for Recall", bg: "bg-amber-500/10 text-amber-700 dark:text-amber-400", border: "border-amber-500/20", icon: Clock };
  }
  if (status === "up_to_date") {
    return { label: "Up to Date", bg: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400", border: "border-emerald-500/20", icon: CheckCircle2 };
  }

  // Fallback calculation if not returned directly
  if (!patient.last_visit_date) {
    return { label: "Due for Recall", bg: "bg-amber-500/10 text-amber-700 dark:text-amber-400", border: "border-amber-500/20", icon: Clock };
  }
  try {
    const daysSince = Math.floor((new Date() - parseISO(patient.last_visit_date)) / (1000 * 60 * 60 * 24));
    if (daysSince >= 150) {
      return { label: "Overdue 60d+", bg: "bg-red-500/10 text-red-700 dark:text-red-400", border: "border-red-500/20", icon: AlertCircle };
    }
    if (daysSince >= 90) {
      return { label: "Due for Recall", bg: "bg-amber-500/10 text-amber-700 dark:text-amber-400", border: "border-amber-500/20", icon: Clock };
    }
  } catch {
    // fallback
  }

  return { label: "Up to Date", bg: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400", border: "border-emerald-500/20", icon: CheckCircle2 };
};

export const PatientDetailsModal = ({
  patient,
  detail,
  loading,
  isOpen,
  onClose,
  onBook,
  onMessage,
  onEdit,
  onRecallTriggered,
  userRole = "owner"
}) => {
  const [activeTab, setActiveTab] = useState("overview");
  const [copiedField, setCopiedField] = useState(null);
  const [recallTriggering, setRecallTriggering] = useState(false);
  const [recallFeedback, setRecallFeedback] = useState(null);
  const [revealedPhi, setRevealedPhi] = useState(null);
  const [revealingPhi, setRevealingPhi] = useState(false);
  const [phiCountdown, setPhiCountdown] = useState(0);

  useEffect(() => {
    let timer;
    if (phiCountdown > 0) {
      timer = setTimeout(() => setPhiCountdown((c) => c - 1), 1000);
    } else if (phiCountdown === 0 && revealedPhi) {
      setRevealedPhi(null);
    }
    return () => clearTimeout(timer);
  }, [phiCountdown, revealedPhi]);

  if (!isOpen || !patient) return null;

  const style = avatarStyle(patient.name || patient.full_name);
  const displayName = revealedPhi?.full_name || patient.name || patient.full_name || "Unknown Patient";
  const displayPhone = revealedPhi?.phone || patient.phone || "—";
  const displayDob = revealedPhi?.dob || detail?.patient?.date_of_birth || detail?.patient?.dob || patient.date_of_birth || patient.dob;
  
  let calculatedAge = null;
  if (displayDob) {
    try {
      calculatedAge = differenceInYears(new Date(), parseISO(displayDob));
    } catch {
      // ignore
    }
  }

  const recallTag = getRecallTag(patient);
  const RecallIcon = recallTag.icon;

  const copyToClipboard = (text, fieldName) => {
    if (!text) return;
    navigator.clipboard.writeText(text);
    setCopiedField(fieldName);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const handleTriggerRecall = async () => {
    setRecallTriggering(true);
    setRecallFeedback(null);
    try {
      // Try v1 API first, fallback to standard router
      let res;
      try {
        res = await api.post(`/patients/${patient.id}/trigger-recall`);
      } catch {
        res = await api.post(`/patients/recall/${patient.id}`);
      }
      setRecallFeedback({ type: "success", message: "CALL-E Voice AI Recall Outreach Triggered!" });
      if (onRecallTriggered) onRecallTriggered(patient.id);
    } catch (err) {
      setRecallFeedback({
        type: "error",
        message: err.response?.data?.detail || err.response?.data?.error || "Failed to trigger recall outreach."
      });
    } finally {
      setRecallTriggering(false);
    }
  };

  const handleRevealPhi = async () => {
    setRevealingPhi(true);
    try {
      const res = await api.post(`/patients/${patient.id}/reveal-phi`, {
        reveal_reason: "Clinical verification and EHR synchronization"
      });
      if (res.data?.data) {
        setRevealedPhi(res.data.data);
        setPhiCountdown(60);
      }
    } catch (err) {
      alert("Unable to decrypt PHI: " + (err.response?.data?.detail || err.message));
    } finally {
      setRevealingPhi(false);
    }
  };

  const appointments = detail?.appointments || [];
  const calls = detail?.calls || [];
  const smsMessages = detail?.smsMessages || [];
  const priorAuths = detail?.priorAuths || detail?.prior_auths || [];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-end bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-2xl h-full bg-surface-container-lowest border-l border-surface-container shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right duration-300">
        
        {/* ── Top Header & Demographics ──────────────────────────────── */}
        <div className="p-6 border-b border-surface-container bg-surface relative">
          <button
            onClick={onClose}
            className="absolute top-5 right-5 p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="flex items-start gap-4 pr-10">
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold flex-shrink-0 shadow-sm"
              style={{ backgroundColor: style.bg, color: style.text }}
            >
              {initials(displayName)}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-2xl font-semibold text-on-surface tracking-tight truncate">
                  {displayName}
                </h2>
                {patient.is_vip && (
                  <span className="px-2 py-0.5 text-xs font-bold bg-amber-500/15 text-amber-600 rounded-full flex items-center gap-1 border border-amber-500/30">
                    <Sparkles className="w-3 h-3" /> VIP
                  </span>
                )}
                <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-full border flex items-center gap-1.5 ${recallTag.bg} ${recallTag.border}`}>
                  {RecallIcon && <RecallIcon className="w-3.5 h-3.5" />}
                  {recallTag.label}
                </span>
              </div>

              {/* Sub-header info */}
              <div className="flex items-center gap-4 mt-2 text-xs text-on-surface-variant flex-wrap">
                {displayDob && (
                  <span>
                    DOB: <strong>{format(parseISO(displayDob), "MMM d, yyyy")}</strong>
                    {calculatedAge !== null && ` (${calculatedAge} yrs)`}
                  </span>
                )}
                <span>
                  Member ID: <strong>{detail?.patient?.insurance_member_id || patient.insurance_member_id || "—"}</strong>
                </span>
                <span>
                  Payer: <strong>{detail?.patient?.insurance_provider || patient.insurance_provider || "Self-Pay"}</strong>
                </span>
              </div>
            </div>
          </div>

          {/* Quick Contact bar */}
          <div className="mt-4 pt-4 border-t border-surface-container/60 grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="flex items-center justify-between bg-surface-container/40 px-3 py-2 rounded-xl text-xs">
              <div className="flex items-center gap-2 truncate">
                <Phone className="w-3.5 h-3.5 text-primary flex-shrink-0" />
                <span className="font-medium text-on-surface">{displayPhone}</span>
              </div>
              <button
                onClick={() => copyToClipboard(displayPhone, "phone")}
                className="text-on-surface-variant hover:text-primary transition-colors p-1"
                title="Copy phone"
              >
                {copiedField === "phone" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              </button>
            </div>

            <div className="flex items-center justify-between bg-surface-container/40 px-3 py-2 rounded-xl text-xs">
              <div className="flex items-center gap-2 truncate">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
                <span className="text-on-surface truncate">
                  {detail?.patient?.email || patient.email || "No email on file"}
                </span>
              </div>
              {(detail?.patient?.email || patient.email) && (
                <button
                  onClick={() => copyToClipboard(detail?.patient?.email || patient.email, "email")}
                  className="text-on-surface-variant hover:text-primary transition-colors p-1"
                  title="Copy email"
                >
                  {copiedField === "email" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              )}
            </div>
          </div>

          {/* Quick Action Toolbar */}
          <div className="flex items-center gap-2 mt-4 flex-wrap">
            <button
              onClick={handleTriggerRecall}
              disabled={recallTriggering || patient.recall_opted_out}
              className="flex-1 sm:flex-none btn-primary text-xs py-2 px-3 flex items-center justify-center gap-1.5 disabled:opacity-50"
              style={{ backgroundColor: "#2e7d32" }}
            >
              {recallTriggering ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Sparkles className="w-3.5 h-3.5 text-amber-300" />
              )}
              Trigger Recall (CALL-E)
            </button>

            <button
              onClick={onMessage}
              className="flex-1 sm:flex-none btn-secondary text-xs py-2 px-3 flex items-center justify-center gap-1.5"
            >
              <MessageSquare className="w-3.5 h-3.5" />
              Send SMS Link
            </button>

            <button
              onClick={onBook}
              className="flex-1 sm:flex-none btn-secondary text-xs py-2 px-3 flex items-center justify-center gap-1.5"
            >
              <Calendar className="w-3.5 h-3.5" />
              Schedule Visit
            </button>

            <button
              onClick={onEdit}
              className="p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg transition-colors"
              title="Edit Profile"
            >
              <Edit className="w-4 h-4" />
            </button>

            {userRole in { owner: 1, clinician: 1, admin: 1 } && !revealedPhi && (
              <button
                onClick={handleRevealPhi}
                disabled={revealingPhi}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-outline-variant/40 hover:bg-surface-container text-on-surface-variant flex items-center gap-1"
                title="Decrypt PHI with HIPAA Audit Log"
              >
                <Eye className="w-3.5 h-3.5 text-primary" />
                {revealingPhi ? "Decrypting..." : "Reveal PHI"}
              </button>
            )}

            {revealedPhi && (
              <span className="text-[0.65rem] font-mono px-2 py-1 bg-amber-500/10 text-amber-700 border border-amber-500/20 rounded-md flex items-center gap-1">
                <Clock className="w-3 h-3 animate-pulse" />
                Decrypted ({phiCountdown}s)
              </span>
            )}
          </div>

          {recallFeedback && (
            <div className={`mt-3 p-2.5 rounded-lg text-xs flex items-center justify-between ${
              recallFeedback.type === "success" ? "bg-emerald-500/10 text-emerald-700 border border-emerald-500/20" : "bg-red-500/10 text-red-700 border border-red-500/20"
            }`}>
              <span>{recallFeedback.message}</span>
              <button onClick={() => setRecallFeedback(null)} className="opacity-70 hover:opacity-100">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* ── Navigation Tabs ────────────────────────────────────────── */}
        <div className="flex border-b border-surface-container px-6 bg-surface-container-lowest">
          {[
            { id: "overview", label: "Overview", icon: HeartPulse },
            { id: "appointments", label: `Appointments (${appointments.length})`, icon: Calendar },
            { id: "prior_auths", label: `Prior Auths (${priorAuths.length})`, icon: FileCheck2 },
            { id: "comms", label: `Voice & SMS (${calls.length + smsMessages.length})`, icon: MessageSquare },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-3 px-4 text-xs font-semibold flex items-center gap-2 border-b-2 transition-all cursor-pointer ${
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-on-surface-variant hover:text-on-surface"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* ── Tab Content ────────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-surface">
          {loading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 bg-surface-container rounded-xl animate-pulse" />
              ))}
            </div>
          ) : (
            <>
              {/* TAB 1: OVERVIEW */}
              {activeTab === "overview" && (
                <div className="space-y-6">
                  {/* Metric Cards */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="bg-surface-container-lowest p-3.5 rounded-xl border border-surface-container">
                      <p className="overline text-on-surface-variant mb-1">Total Visits</p>
                      <p className="text-xl font-bold text-on-surface">{detail?.patient?.total_visits ?? patient.total_visits ?? patient.visit_count ?? 0}</p>
                    </div>
                    <div className="bg-surface-container-lowest p-3.5 rounded-xl border border-surface-container">
                      <p className="overline text-on-surface-variant mb-1">Last Visit</p>
                      <p className="text-sm font-semibold text-on-surface mt-1">
                        {(detail?.patient?.last_visit_date || patient.last_visit_date) ? format(parseISO(detail?.patient?.last_visit_date || patient.last_visit_date), "MMM d, yyyy") : "None"}
                      </p>
                    </div>
                    <div className="bg-surface-container-lowest p-3.5 rounded-xl border border-surface-container">
                      <p className="overline text-on-surface-variant mb-1">Lifetime Value</p>
                      <p className="text-xl font-bold text-primary">
                        ${Number(detail?.patient?.total_revenue_generated ?? patient?.total_revenue_generated ?? (patient?.total_revenue_cents ? patient.total_revenue_cents / 100 : 0)).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                      </p>
                    </div>
                    <div className="bg-surface-container-lowest p-3.5 rounded-xl border border-surface-container">
                      <p className="overline text-on-surface-variant mb-1">No-Shows</p>
                      <p className={`text-xl font-bold ${Number(detail?.patient?.no_show_count ?? patient.no_show_count ?? 0) > 0 ? "text-red-600" : "text-emerald-600"}`}>
                        {detail?.patient?.no_show_count ?? patient.no_show_count ?? 0}
                      </p>
                    </div>
                  </div>

                  {/* Demographics & Insurance Summary */}
                  <div className="bg-surface-container-lowest p-4 rounded-xl border border-surface-container">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-primary mb-3">EHR & Insurance Record</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                      <div>
                        <span className="text-on-surface-variant block mb-0.5">Insurance Payer</span>
                        <span className="font-semibold text-on-surface text-sm">
                          {detail?.patient?.insurance_provider || patient.insurance_provider || "Self-Pay / Not specified"}
                        </span>
                      </div>
                      <div>
                        <span className="text-on-surface-variant block mb-0.5">Member Policy ID</span>
                        <span className="font-semibold text-on-surface text-sm font-mono">
                          {detail?.patient?.insurance_member_id || patient.insurance_member_id || "—"}
                        </span>
                      </div>
                      <div>
                        <span className="text-on-surface-variant block mb-0.5">Preferred Recall Timing</span>
                        <span className="font-semibold text-on-surface capitalize">
                          {detail?.patient?.preferred_time || patient.preferred_time || "Morning"}
                        </span>
                      </div>
                      <div>
                        <span className="text-on-surface-variant block mb-0.5">Auto-Recall Calling Status</span>
                        <span className={`font-semibold ${patient.recall_opted_out ? "text-red-600" : "text-emerald-600"}`}>
                          {patient.recall_opted_out ? "Exempt / Opted Out" : "Active for CALL-E AI Outreach"}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Notes Section */}
                  {(detail?.patient?.notes || patient.notes) && (
                    <div className="bg-amber-500/5 p-4 rounded-xl border border-amber-500/20">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-amber-700 dark:text-amber-400 mb-1.5">
                        Clinical & Patient Notes
                      </h4>
                      <p className="text-xs text-on-surface leading-relaxed">
                        {detail?.patient?.notes || patient.notes}
                      </p>
                    </div>
                  )}

                  {/* Recent Activity Snapshot */}
                  <div>
                    <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                      Recent Timeline
                    </h4>
                    <div className="space-y-2.5">
                      {appointments.slice(0, 2).map((apt) => (
                        <div key={apt.id} className="p-3 bg-surface-container-lowest rounded-xl border border-surface-container flex items-center justify-between text-xs">
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center font-bold">
                              <Calendar className="w-4 h-4" />
                            </div>
                            <div>
                              <p className="font-semibold text-on-surface">{apt.appointment_type || "Evaluation"}</p>
                              <p className="text-on-surface-variant text-[0.7rem]">
                                {apt.datetime || apt.slot_start ? format(parseISO(apt.datetime || apt.slot_start), "MMM d, yyyy · h:mm a") : "—"}
                              </p>
                            </div>
                          </div>
                          <span className={`px-2 py-0.5 text-[0.65rem] font-bold rounded-full uppercase ${
                            apt.status === "completed" ? "bg-emerald-500/10 text-emerald-700" : "bg-blue-500/10 text-blue-700"
                          }`}>
                            {apt.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: APPOINTMENT HISTORY */}
              {activeTab === "appointments" && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                      All Visits & Consultations ({appointments.length})
                    </h4>
                    <button onClick={onBook} className="btn-primary text-xs py-1.5 px-3">
                      + Schedule Visit
                    </button>
                  </div>

                  {appointments.length === 0 ? (
                    <div className="p-10 text-center bg-surface-container-lowest rounded-xl border border-surface-container">
                      <Calendar className="w-8 h-8 text-on-surface-variant/40 mx-auto mb-2" />
                      <p className="text-sm font-semibold text-on-surface">No appointments found</p>
                      <p className="text-xs text-on-surface-variant mt-1">Schedule their first appointment now.</p>
                    </div>
                  ) : (
                    appointments.map((apt) => (
                      <div key={apt.id} className="p-4 bg-surface-container-lowest rounded-xl border border-surface-container flex items-start justify-between gap-4">
                        <div className="flex items-start gap-3">
                          <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${
                            apt.status === "completed" ? "bg-emerald-500/15 text-emerald-700" : "bg-blue-500/15 text-blue-700"
                          }`}>
                            <CheckCircle2 className="w-5 h-5" />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-on-surface">{apt.appointment_type || "Clinic Visit"}</p>
                            <p className="text-xs text-on-surface-variant mt-0.5 flex items-center gap-2">
                              <span>{apt.datetime || apt.slot_start ? format(parseISO(apt.datetime || apt.slot_start), "EEEE, MMM d, yyyy · h:mm a") : "—"}</span>
                              {apt.revenue_amount && <span>· ${apt.revenue_amount}</span>}
                            </p>
                            {apt.notes && (
                              <p className="text-xs text-on-surface-variant/80 mt-2 bg-surface-container/40 p-2 rounded-lg">
                                {apt.notes}
                              </p>
                            )}
                          </div>
                        </div>
                        <span className={`px-2.5 py-1 text-xs font-bold rounded-full uppercase tracking-wider flex-shrink-0 ${
                          apt.status === "completed" ? "bg-emerald-500/10 text-emerald-700" :
                          apt.status === "confirmed" ? "bg-blue-500/10 text-blue-700" :
                          apt.status === "cancelled" ? "bg-red-500/10 text-red-700" :
                          "bg-surface-container text-on-surface-variant"
                        }`}>
                          {apt.status}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* TAB 3: PRIOR AUTHORIZATION HISTORY */}
              {activeTab === "prior_auths" && (
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-2">
                    Prior Authorization Claims & CALL-E Verification
                  </h4>

                  {priorAuths.length === 0 ? (
                    <div className="p-10 text-center bg-surface-container-lowest rounded-xl border border-surface-container">
                      <FileCheck2 className="w-8 h-8 text-on-surface-variant/40 mx-auto mb-2" />
                      <p className="text-sm font-semibold text-on-surface">No prior authorization claims on file</p>
                      <p className="text-xs text-on-surface-variant mt-1">Claims created in Prior Auth manager will appear here.</p>
                    </div>
                  ) : (
                    priorAuths.map((pa) => (
                      <div key={pa.id} className="p-4 bg-surface-container-lowest rounded-xl border border-surface-container space-y-2">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold px-2 py-0.5 bg-primary/10 text-primary rounded font-mono">
                                CPT: {pa.cpt_code || "General"}
                              </span>
                              <span className="text-sm font-semibold text-on-surface">
                                {pa.cpt_description || "Specialty Procedure"}
                              </span>
                            </div>
                            <p className="text-xs text-on-surface-variant mt-1">
                              Target Date: {pa.requested_service_date ? format(parseISO(pa.requested_service_date), "MMM d, yyyy") : "Standard"}
                              {pa.authorization_number && ` · Auth #: ${pa.authorization_number}`}
                            </p>
                          </div>

                          <div className="text-right flex-shrink-0">
                            <span className={`px-2.5 py-1 text-xs font-bold rounded-full uppercase tracking-wider ${
                              pa.auth_status === "approved" ? "bg-emerald-500/10 text-emerald-700" :
                              pa.auth_status === "denied" ? "bg-red-500/10 text-red-700" :
                              "bg-amber-500/10 text-amber-700"
                            }`}>
                              {pa.auth_status || "Pending"}
                            </span>
                            {pa.calle_task_id && (
                              <p className="text-[0.65rem] text-primary font-mono mt-1">
                                CALL-E Task: {pa.call_status || "synced"}
                              </p>
                            )}
                          </div>
                        </div>

                        {pa.denial_reason && (
                          <div className="p-2.5 bg-red-500/5 text-red-700 border border-red-500/20 rounded-lg text-xs">
                            <strong>Payer Denial:</strong> {pa.denial_reason}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* TAB 4: VOICE & SMS COMMUNICATIONS */}
              {activeTab === "comms" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                      AI Voice Calls & SMS Logs
                    </h4>
                    <button onClick={onMessage} className="btn-secondary text-xs py-1.5 px-3 flex items-center gap-1">
                      <Send className="w-3 h-3" /> New SMS
                    </button>
                  </div>

                  {calls.length === 0 && smsMessages.length === 0 ? (
                    <div className="p-10 text-center bg-surface-container-lowest rounded-xl border border-surface-container">
                      <MessageSquare className="w-8 h-8 text-on-surface-variant/40 mx-auto mb-2" />
                      <p className="text-sm font-semibold text-on-surface">No communications recorded yet</p>
                      <p className="text-xs text-on-surface-variant mt-1">Automated recall calls and SMS replies will stream here.</p>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {/* Voice Calls */}
                      {calls.map((call) => (
                        <div key={call.id} className="p-3.5 bg-surface-container-lowest rounded-xl border border-surface-container">
                          <div className="flex items-center justify-between text-xs mb-1.5">
                            <span className="font-bold flex items-center gap-1.5 text-primary">
                              <Phone className="w-3.5 h-3.5" />
                              {call.direction === "outbound" ? "↗ Outbound Recall (CALL-E AI)" : "↙ Inbound Patient Call"}
                            </span>
                            <span className="text-on-surface-variant">
                              {call.started_at || call.created_at ? format(parseISO(call.started_at || call.created_at), "MMM d, h:mm a") : "—"}
                            </span>
                          </div>
                          <p className="text-xs text-on-surface leading-relaxed">
                            {call.transcript
                              ? call.transcript
                              : `${call.call_type || "Outreach"} call completed (${call.duration_seconds || 0}s). Outcome: ${call.outcome || "completed"}`}
                          </p>
                        </div>
                      ))}

                      {/* SMS Messages */}
                      {smsMessages.map((sms) => (
                        <div
                          key={sms.id}
                          className={`p-3 rounded-xl text-xs max-w-[90%] ${
                            sms.direction === "inbound"
                              ? "bg-surface-container text-on-surface rounded-tl-sm mr-auto"
                              : "bg-emerald-500/10 text-emerald-900 dark:text-emerald-300 border border-emerald-500/20 rounded-tr-sm ml-auto"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-3 text-[0.65rem] opacity-70 mb-1">
                            <span>{sms.direction === "inbound" ? "📩 Patient SMS" : "📤 AI / Clinic Outbound"}</span>
                            <span>{sms.created_at ? format(parseISO(sms.created_at), "h:mm a · MMM d") : ""}</span>
                          </div>
                          <p className="text-xs leading-relaxed">{sms.body}</p>
                          {sms.reply_sentiment && (
                            <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-[0.55rem] font-bold uppercase bg-surface-container-highest">
                              Sentiment: {sms.reply_sentiment}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default PatientDetailsModal;
