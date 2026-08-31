import React, { useEffect, useState, useCallback, useRef, useMemo } from "react";
import {
  Calendar,
  Clock,
  Plus,
  CheckCircle,
  XCircle,
  AlertCircle,
  RefreshCw,
  CalendarDays,
  Bot,
  User,
  FileText,
  X,
  Sparkles,
  Phone,
  Users,
  Maximize2,
  Shield,
  ShieldCheck,
  ShieldX,
  ShieldAlert,
  Volume2,
  Play,
  Pause,
  Loader,
  Save,
  Check,
  PhoneCall,
  Sliders,
  Search,
  Stethoscope,
  ChevronLeft,
  ChevronRight,
  Filter,
  Send,
  Lock,
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useWebSocket } from "../context/WebSocketContext";
import { translations } from "../lib/translations";
import { useLocation } from "react-router-dom";
import {
  format,
  parseISO,
  isToday,
  isTomorrow,
  startOfDay,
  endOfDay,
  addDays,
} from "date-fns";
import AppointmentModal from "../components/AppointmentModal";

const DEFAULT_TZ = "America/Chicago";

/* ─── Eligibility Status Badge ─────────────────────────────────────── */
const ELIG_CONFIG = {
  active:     { label: "Active",      color: "#396a00", bg: "rgba(127,205,77,0.12)",   border: "rgba(127,205,77,0.3)",   glow: "none", Icon: ShieldCheck, dot: "#396a00" },
  inactive:   { label: "Inactive",    color: "#b71c1c", bg: "rgba(183,28,28,0.08)",   border: "rgba(183,28,28,0.2)",    glow: "none", Icon: ShieldX,     dot: "#b71c1c" },
  unverified: { label: "Unverified",  color: "#585d77", bg: "rgba(88,93,119,0.06)",   border: "rgba(88,93,119,0.15)",  glow: "none", Icon: Shield,      dot: "#585d77" },
  error:      { label: "Mismatch",    color: "#9a6800", bg: "rgba(154,104,0,0.08)",   border: "rgba(154,104,0,0.2)",    glow: "none", Icon: ShieldAlert, dot: "#9a6800" },
};

const EligibilityBadge = ({ status, priorAuth, small = false }) => {
  const cfg = ELIG_CONFIG[status] || ELIG_CONFIG.unverified;
  const paddingStr = small ? "px-2 py-0.5" : "px-2.5 py-1";
  const textStr = small ? "text-[0.65rem]" : "text-[0.7rem]";
  return (
    <span
      className={`inline-flex items-center gap-1 font-bold rounded-md border transition-all ${paddingStr} ${textStr}`}
      style={{
        color: cfg.color,
        backgroundColor: cfg.bg,
        borderColor: cfg.border
      }}
    >
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: cfg.dot }} />
      {cfg.label}
      {priorAuth && (
        <span className="ml-1 px-1 rounded-md bg-amber-500/10 text-amber-600 text-[0.6rem] font-extrabold border border-amber-500/20">
          PA
        </span>
      )}
    </span>
  );
};

const fmtClinicTime = (iso, tz = DEFAULT_TZ) => {
  if (!iso) return "--:-- --";
  try {
    return new Date(iso).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: tz,
    });
  } catch {
    return "--:-- --";
  }
};

const getTzAbbr = (iso, tz = DEFAULT_TZ) => {
  if (!iso) return "";
  try {
    const formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      timeZoneName: "short",
    });
    const parts = formatter.formatToParts(new Date(iso));
    const tzPart = parts.find((p) => p.type === "timeZoneName");
    return tzPart ? tzPart.value : "";
  } catch {
    return "";
  }
};

const fmtClinicDate = (iso, tz = DEFAULT_TZ) => {
  if (!iso) return "Unknown";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      weekday: "long",
      month: "long",
      day: "numeric",
      timeZone: tz,
    });
  } catch {
    return "Unknown";
  }
};

const clinicDateKey = (iso, tz = DEFAULT_TZ) => {
  if (!iso) return "unknown";
  try {
    return new Date(iso).toLocaleDateString("en-CA", { timeZone: tz });
  } catch {
    return "unknown";
  }
};

/* ── Status config ──────────────────────────────────────────── */
const STATUS_CFG = {
  scheduled: { label: "SCHEDULED", bg: "#e3f2fd", textColor: "#006493", dotColor: "#006493" },
  confirmed: { label: "CONFIRMED", bg: "#edf7e0", textColor: "#396a00", dotColor: "#396a00" },
  cancelled: { label: "CANCELLED", bg: "#fce4ec", textColor: "#b71c1c", dotColor: "#b71c1c" },
  completed: { label: "COMPLETED", bg: "#ede7f6", textColor: "#4a148c", dotColor: "#4a148c" },
  no_show:   { label: "NO-SHOW",   bg: "#fff3e0", textColor: "#b45309", dotColor: "#b45309" },
};

const StatusBadge = ({ status }) => {
  const cfg = STATUS_CFG[status] || STATUS_CFG.scheduled;
  return (
    <div
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[0.625rem] font-bold tracking-wider"
      style={{ backgroundColor: cfg.bg, color: cfg.textColor }}
    >
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: cfg.dotColor }} />
      <span>{cfg.label}</span>
    </div>
  );
};

/* ── Avatar helpers ──────────────────────────────────────────── */
const initials = (name) =>
  (name || "?").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();
const AVATAR_COLORS = ["#d4e8c1", "#c8d9e8", "#e8d4c1", "#d4c1e8", "#c1e8d4", "#fde68a", "#fbcfe8"];
const avatarColor = (name) => AVATAR_COLORS[(name?.charCodeAt(0) || 0) % AVATAR_COLORS.length];

/* ── Custom Audio Player ────────────────────────────────────── */
const CustomAudioPlayer = ({ src }) => {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const onTimeUpdate = () => setCurrentTime(audio.currentTime);
    const onLoadedMetadata = () => setDuration(audio.duration);
    const onEnded = () => setIsPlaying(false);

    audio.addEventListener("timeupdate", onTimeUpdate);
    audio.addEventListener("loadedmetadata", onLoadedMetadata);
    audio.addEventListener("ended", onEnded);

    if (audio.readyState >= 1) {
      setDuration(audio.duration);
    }

    return () => {
      audio.removeEventListener("timeupdate", onTimeUpdate);
      audio.removeEventListener("loadedmetadata", onLoadedMetadata);
      audio.removeEventListener("ended", onEnded);
    };
  }, [src]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleScrub = (e) => {
    const time = Number(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const formatTime = (time) => {
    if (isNaN(time)) return "0:00";
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div className="flex items-center gap-3 bg-slate-50 border border-slate-200 rounded-xl p-3 shadow-inner">
      <audio ref={audioRef} src={src} preload="metadata" className="hidden" />
      <button
        type="button"
        onClick={togglePlay}
        className="w-8 h-8 rounded-xl bg-[#396a00] text-white flex items-center justify-center hover:scale-105 active:scale-95 transition-all duration-200 shadow-md shadow-[#396a00]/20 flex-shrink-0 border-none cursor-pointer"
      >
        {isPlaying ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current ml-0.5" />}
      </button>

      <div className="flex-1 min-w-0">
        <input
          type="range"
          min={0}
          max={duration || 100}
          value={currentTime}
          onChange={handleScrub}
          className="w-full h-1 rounded-lg bg-slate-200 appearance-none cursor-pointer accent-[#396a00] border-none outline-none focus:ring-0"
        />
        <div className="flex justify-between items-center mt-1.5 text-[9px] text-on-surface-variant font-mono">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>
    </div>
  );
};

/* ── Detail Panel ───────────────────────────────────────────── */
const AppointmentDetailPanel = ({
  appointment,
  call,
  patient,
  loadingCall,
  loadingPatient,
  onClose,
  onUpdateStatus,
  onUpdateInsurance,
  onUpdateNotes,
  onTriggerConfirmationCall,
  onMaximize,
  updatingId,
  isTriggeringCall,
  timezone = DEFAULT_TZ,
}) => {
  const [activeSubTab, setActiveSubTab] = useState("transcript");
  const [noteText, setNoteText] = useState("");
  const [isSavingNote, setIsSavingNote] = useState(false);

  useEffect(() => {
    if (appointment) {
      setNoteText(appointment.notes || "");
    }
  }, [appointment]);

  if (!appointment) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-on-surface-variant p-8 text-center bg-white">
        <div className="w-14 h-14 bg-slate-50 border border-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-sm animate-pulse">
          <CalendarDays className="w-6 h-6 text-slate-400" />
        </div>
        <p className="font-bold text-on-surface text-sm tracking-tight">No Appointment Selected</p>
        <p className="text-[11px] mt-1 text-on-surface-variant/80 max-w-[220px] leading-relaxed">
          Select any appointment from the list or calendar to view its complete patient profile, call transcript, and status actions.
        </p>
      </div>
    );
  }

  const handleSaveNote = async () => {
    setIsSavingNote(true);
    await onUpdateNotes(appointment.id, noteText);
    setIsSavingNote(false);
  };

  const lines = call?.transcript
    ? call.transcript.split("\n").map((l) => l.trim()).filter(Boolean)
    : [];

  return (
    <div className="h-full flex flex-col overflow-hidden bg-white select-none">
      {/* Header */}
      <div className="p-5 border-b border-[#edf1ef] flex-shrink-0 bg-white">
        <div className="flex items-start justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-[0.6rem] font-black tracking-widest text-[#396a00] uppercase bg-[#7FCD4D]/15 px-2 py-0.5 rounded-md">
                APPOINTMENT PROFILE
              </span>
              <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
              {appointment.noshow_risk >= 0.5 && (
                <span className="text-[0.55rem] font-extrabold px-1.5 py-0.5 rounded-md bg-red-100 text-red-800 animate-pulse">
                  ⚠️ HIGH NO-SHOW RISK
                </span>
              )}
            </div>
            <h3 className="font-extrabold text-base text-[#181c1c] tracking-tight truncate">
              {appointment.patient_name}
            </h3>
            <p className="text-xs text-on-surface-variant mt-0.5 flex items-center gap-1.5 font-medium">
              <span>{appointment.appointment_type}</span>
              <span className="text-slate-300">•</span>
              <span>{fmtClinicTime(appointment.datetime, timezone)}</span>
              {appointment.doctor_name && (
                <>
                  <span className="text-slate-300">•</span>
                  <span className="text-[#396a00] font-bold">{appointment.doctor_name}</span>
                </>
              )}
            </p>
          </div>
          <div className="flex items-center gap-1 flex-shrink-0">
            <button
              onClick={onMaximize}
              title="Open Dedicated Clinical Modal"
              className="p-1.5 text-on-surface-variant hover:text-[#396a00] hover:bg-slate-50 rounded-lg transition-all border-none bg-transparent cursor-pointer"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-on-surface-variant hover:text-[#181c1c] hover:bg-slate-50 rounded-lg transition-all hover:rotate-90 border-none bg-transparent cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Quick Action Status Bar */}
      <div className="px-5 py-2.5 bg-slate-50 border-b border-[#edf1ef] flex flex-wrap gap-2 items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider">Status:</span>
          <select
            value={appointment.status}
            onChange={(e) => onUpdateStatus(appointment.id, e.target.value)}
            disabled={updatingId === appointment.id}
            className="text-xs font-semibold px-2 py-1 rounded-md bg-white border border-[#bec9c4] outline-none cursor-pointer hover:bg-slate-50 transition-all font-sans"
          >
            <option value="scheduled">Scheduled</option>
            <option value="confirmed">Confirmed</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No-Show</option>
          </select>
        </div>

        {/* Trigger CALL-E confirmation call button */}
        <button
          onClick={() => onTriggerConfirmationCall(appointment)}
          disabled={isTriggeringCall}
          className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-[#396a00] border border-emerald-200 transition-all cursor-pointer flex items-center gap-1.5"
          title="Place automated CALL-E 24h confirmation call now"
        >
          {isTriggeringCall ? (
            <Loader className="w-3 h-3 animate-spin" />
          ) : (
            <Bot className="w-3 h-3 text-[#396a00]" />
          )}
          <span>Trigger CALL-E Call</span>
        </button>
      </div>

      {/* Tab Selectors */}
      <div className="flex border-b border-[#edf1ef] bg-white flex-shrink-0">
        <button
          onClick={() => setActiveSubTab("transcript")}
          className={`flex-1 py-2.5 text-center text-xs font-bold border-b-2 transition-all border-none bg-transparent cursor-pointer ${
            activeSubTab === "transcript"
              ? "border-b-2 border-solid border-[#396a00] text-[#396a00]"
              : "text-on-surface-variant hover:text-[#181c1c] hover:bg-slate-50"
          }`}
        >
          Call & AI Summary
        </button>
        <button
          onClick={() => setActiveSubTab("patientDetails")}
          className={`flex-1 py-2.5 text-center text-xs font-bold border-b-2 transition-all border-none bg-transparent cursor-pointer ${
            activeSubTab === "patientDetails"
              ? "border-b-2 border-solid border-[#396a00] text-[#396a00]"
              : "text-on-surface-variant hover:text-[#181c1c] hover:bg-slate-50"
          }`}
        >
          Patient Profile
        </button>
      </div>

      {/* Panel Scroll Container */}
      <div className="flex-1 overflow-y-auto thin-scrollbar p-5 space-y-5">
        {appointment.conflict && (
          <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl flex gap-2.5 items-start text-xs text-amber-950 select-none shadow-sm mb-1">
            <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5 animate-pulse" />
            <div>
              <p className="font-bold text-amber-950">Active Scheduling Conflict</p>
              <p className="opacity-90 mt-1 leading-relaxed font-semibold">
                This slot overlaps with <span className="font-bold">{
                  appointment.conflict.patient_name.startsWith("[BLOCKED]")
                    ? appointment.conflict.patient_name.replace("[BLOCKED] ", "")
                    : appointment.conflict.patient_name
                }</span> ({fmtClinicTime(appointment.conflict.datetime, timezone)}). Please reschedule or cancel one of these appointments to resolve the conflict.
              </p>
            </div>
          </div>
        )}

        {activeSubTab === "transcript" && (
          <>
            {loadingCall ? (
              <div className="py-12 flex items-center justify-center">
                <Loader className="w-5 h-5 text-[#396a00] animate-spin" />
              </div>
            ) : call ? (
              <div className="space-y-4">
                {/* Insights Bento Card */}
                <div className="bg-white border border-[#edf1ef] rounded-2xl p-4 shadow-sm relative overflow-hidden">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="w-6 h-6 rounded-lg bg-[#7FCD4D]/10 flex items-center justify-center">
                      <Sparkles className="w-3.5 h-3.5 text-[#396a00]" />
                    </div>
                    <span className="text-xs font-bold text-[#181c1c]">AI Call Insights</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Call Intent</p>
                      <p className="text-xs font-bold text-[#181c1c] mt-0.5 capitalize">{call.call_type || "Booking"}</p>
                    </div>
                    <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Sentiment</p>
                      <span className="inline-block mt-0.5 px-2 py-0.5 text-[9px] font-bold rounded-md bg-emerald-100 text-emerald-800">
                        Positive
                      </span>
                    </div>
                  </div>

                  <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                    <p className="text-[9px] font-bold text-slate-400 uppercase mb-1">AI Conversation Brief</p>
                    <p className="text-xs text-[#3d4946] leading-relaxed font-medium">
                      {call.transcript
                        ? call.transcript.slice(0, 240) + (call.transcript.length > 240 ? "..." : "")
                        : "No call transcript summary parsed. Patient booked appointment via phone call."}
                    </p>
                  </div>
                </div>

                {/* Call Audio Player */}
                {call.recording_url && (
                  <div className="space-y-1.5">
                    <label className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block">CALL RECORDING</label>
                    <CustomAudioPlayer src={call.recording_url} />
                  </div>
                )}

                {/* Call Meta Info */}
                <div className="flex justify-between text-[10px] text-on-surface-variant font-semibold bg-slate-50 rounded-xl p-2.5 border border-slate-100">
                  <span className="flex items-center gap-1">
                    <PhoneCall className="w-3 h-3 text-[#396a00]" /> {call.from_number || "Inbound"}
                  </span>
                  <span>Duration: {call.duration_seconds ? `${Math.floor(call.duration_seconds / 60)}m ${call.duration_seconds % 60}s` : "-"}</span>
                </div>

                {/* Speech Transcript logs */}
                <div className="space-y-2">
                  <label className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block">TRANSCRIPT LOGS</label>
                  <div className="space-y-3 bg-white border border-[#edf1ef] rounded-2xl p-4 max-h-[250px] overflow-y-auto thin-scrollbar">
                    {lines.length > 0 ? (
                      lines.map((line, i) => {
                        const isAgent = /^(agent|receptionist):/i.test(line);
                        const text = line.replace(/^(agent|user|patient|caller|receptionist):\s*/i, "");
                        return (
                          <div key={i} className="flex gap-2.5">
                            <div
                              className="w-6 h-6 rounded-md flex items-center justify-center text-[8px] font-black flex-shrink-0 mt-0.5 shadow-sm"
                              style={isAgent
                                ? { backgroundColor: "#edf7e0", color: "#396a00" }
                                : { backgroundColor: "#e3f2fd", color: "#006493" }}
                            >
                              {isAgent ? "AI" : "PT"}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs text-[#181c1c] leading-relaxed font-medium">{text || line}</p>
                            </div>
                          </div>
                        );
                      })
                    ) : (
                      <div className="flex flex-col items-center justify-center py-6 text-slate-300">
                        <FileText className="w-7 h-7 mb-1 opacity-40" />
                        <p className="text-[10px] font-semibold">No speech transcript recorded</p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-10 text-center bg-slate-50 border border-dashed border-slate-200 rounded-2xl">
                <Bot className="w-8 h-8 mx-auto text-slate-300 mb-2 animate-pulse" />
                <p className="text-xs font-bold text-[#181c1c]">No Call Record Found</p>
                <p className="text-[10px] text-on-surface-variant mt-1 max-w-[200px] mx-auto leading-relaxed">
                  This appointment was created manually by staff and does not have an AI call record.
                </p>
              </div>
            )}
          </>
        )}

        {activeSubTab === "patientDetails" && (
          <>
            {loadingPatient ? (
              <div className="py-12 flex items-center justify-center">
                <Loader className="w-5 h-5 text-[#396a00] animate-spin" />
              </div>
            ) : patient ? (
              <div className="space-y-4">
                {/* Demographics */}
                <div className="bg-white border border-[#edf1ef] rounded-2xl p-4 shadow-sm space-y-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold border border-slate-100 text-[#181c1c]"
                      style={{ backgroundColor: avatarColor(patient.patient?.name) }}
                    >
                      {initials(patient.patient?.name)}
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-[#181c1c]">{patient.patient?.name}</h4>
                      <p className="text-[9px] text-on-surface-variant font-medium mt-0.5">
                        Last Seen: {patient.patient?.last_visit_date || "First-time patient"}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 pt-3 border-t border-[#edf1ef] text-xs font-medium">
                    <div>
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Phone</p>
                      <p className="text-xs text-[#181c1c] mt-0.5">{patient.patient?.phone || "-"}</p>
                    </div>
                    <div>
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Email</p>
                      <p className="text-xs text-[#181c1c] mt-0.5 truncate">{patient.patient?.email || "-"}</p>
                    </div>
                    <div>
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Date of Birth</p>
                      <p className="text-xs text-[#181c1c] mt-0.5">{patient.patient?.date_of_birth || "-"}</p>
                    </div>
                    <div>
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Recall Status</p>
                      <span className={`inline-block mt-0.5 px-2 py-0.5 text-[9px] font-bold rounded-md ${
                        patient.patient?.recall_opted_out ? "bg-red-100 text-red-800" : "bg-emerald-100 text-emerald-800"
                      }`}>
                        {patient.patient?.recall_opted_out ? "Opted Out" : "Active Recall"}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Insurance Details */}
                <div className="bg-white border border-[#edf1ef] rounded-2xl p-4 shadow-sm space-y-3">
                  <div className="flex items-center gap-2">
                    <Shield className="w-4 h-4 text-[#396a00]" />
                    <span className="text-xs font-bold text-[#181c1c]">Insurance Coverage</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-medium pt-2 border-t border-[#edf1ef]">
                    <div>
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Provider</p>
                      <p className="text-xs text-[#181c1c] mt-0.5">{patient.patient?.insurance_provider || "Unassigned"}</p>
                    </div>
                    <div>
                      <p className="text-[8px] font-bold text-slate-400 uppercase">Member ID</p>
                      <p className="text-xs font-mono text-[#181c1c] mt-0.5">{patient.patient?.insurance_member_id || "-"}</p>
                    </div>
                  </div>
                </div>

                {/* Past Visits logs */}
                <div className="space-y-2">
                  <label className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block">PATIENT VISIT LOGS ({patient.appointments?.length || 0})</label>
                  <div className="space-y-2 max-h-[200px] overflow-y-auto thin-scrollbar">
                    {patient.appointments && patient.appointments.length > 0 ? (
                      patient.appointments.map((apt) => (
                        <div key={apt.id} className="flex justify-between items-center bg-slate-50 border border-slate-100 rounded-xl p-2.5 text-xs hover:bg-[#f7faf9] transition-all">
                          <div>
                            <p className="font-bold text-[#181c1c]">{apt.appointment_type}</p>
                            <p className="text-[9px] text-on-surface-variant font-medium mt-0.5">{new Date(apt.datetime).toLocaleDateString()}</p>
                          </div>
                          <span className={`px-2 py-0.5 text-[9px] font-extrabold rounded-md uppercase ${
                            apt.status === "completed" ? "bg-emerald-100 text-emerald-800" :
                            apt.status === "cancelled" ? "bg-red-100 text-red-800" : "bg-blue-100 text-blue-800"
                          }`}>
                            {apt.status}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-on-surface-variant/60 text-center py-4 bg-slate-50 border border-dashed rounded-xl font-medium">
                        No prior appointments booked
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-8 text-center text-xs text-on-surface-variant font-medium">No profile loaded</div>
            )}
          </>
        )}

        {/* Clinical notes card */}
        <div className="border-t border-[#edf1ef] pt-4 space-y-2">
          <label className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block">APPOINTMENT CLINICAL NOTES</label>
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-3 shadow-inner space-y-2">
            <textarea
              className="w-full bg-transparent text-xs outline-none resize-none text-[#181c1c] placeholder:text-on-surface-variant/40 leading-relaxed min-h-[70px]"
              placeholder="Type clinical summary, doctor instructions, or special requests here..."
              value={noteText}
              onChange={(e) => setNoteText(e.target.value)}
            />
            <div className="flex justify-end pt-1">
              <button
                type="button"
                onClick={handleSaveNote}
                disabled={isSavingNote || noteText === (appointment.notes || "")}
                className="btn-primary text-[10px] px-3 py-1.5 font-bold flex items-center gap-1 disabled:opacity-40 border-none cursor-pointer"
              >
                {isSavingNote ? <Loader className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                Save Note
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ── MAIN APPOINTMENTS COMPONENT ────────────────────────────── */
const Appointments = () => {
  const { getCacheItem, setCacheItem, language } = useAuth();
  const t = translations[language] || translations.en;
  const location = useLocation();

  // Primary states
  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState(null);
  const [isTriggeringCall, setIsTriggeringCall] = useState(false);
  const [showNewModal, setShowNewModal] = useState(false);
  const [toast, setToast] = useState(null);
  const [viewMode, setViewMode] = useState("calendar");
  const [currentMonthDate, setCurrentMonthDate] = useState(new Date());
  const [prefilledDate, setPrefilledDate] = useState("");

  // Filters
  const [activeDateTab, setActiveDateTab] = useState("today"); // today | upcoming | all | custom
  const [selectedDoctor, setSelectedDoctor] = useState("all");
  const [selectedStatus, setSelectedStatus] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [customDateFrom, setCustomDateFrom] = useState("");
  const [customDateTo, setCustomDateTo] = useState("");

  // Detail drawer states
  const [selectedAppt, setSelectedAppt] = useState(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [apptCall, setApptCall] = useState(null);
  const [callLoading, setCallLoading] = useState(false);
  const [apptPatient, setApptPatient] = useState(null);
  const [patientLoading, setPatientLoading] = useState(false);

  // Clinic & providers
  const [clinic, setClinic] = useState(null);
  const [doctorsList, setDoctorsList] = useState([
    { id: "doc-1", name: "Dr. Sarah Jenkins", specialty: "General Practice" },
    { id: "doc-2", name: "Dr. Alex Taylor", specialty: "Internal Medicine" },
    { id: "doc-3", name: "Dr. Michael Chang", specialty: "Cardiology" },
  ]);

  const { isConnected, lastEvent } = useWebSocket();

  const showToast = useCallback((msg, type = "success") => {
    setToast({ msg, type });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    if (params.get("new") === "true") {
      setShowNewModal(true);
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [location.search]);

  // Fetch Clinic Profile & Staff/Doctors
  const fetchClinicStatus = useCallback(async () => {
    try {
      const info = JSON.parse(localStorage.getItem("clinic-info") || sessionStorage.getItem("clinic-info") || "{}");
      if (info.clinicId) {
        const cachedClinic = getCacheItem(`clinic:${info.clinicId}`);
        if (cachedClinic) {
          setClinic(cachedClinic);
        }
        const res = await api.get(`/clinics/${info.clinicId}`);
        const clinicData = res.data?.data || null;
        setClinic(clinicData);
        setCacheItem(`clinic:${info.clinicId}`, clinicData);
      }

      // Fetch Staff for Doctor Dropdown
      try {
        const staffRes = await api.get("/staff");
        if (staffRes.data?.data && Array.isArray(staffRes.data.data)) {
          const docs = staffRes.data.data
            .filter((s) => ["doctor", "owner", "clinician", "physician", "provider"].includes((s.role || "").toLowerCase()))
            .map((s) => ({
              id: s.id || s.user_id,
              name: s.name || s.email,
              specialty: s.role === "owner" ? "Lead Clinician" : (s.specialty || "Physician"),
            }));
          if (docs.length > 0) {
            setDoctorsList(docs);
          }
        }
      } catch (staffErr) {
        console.warn("Could not fetch dynamic staff list:", staffErr);
      }
    } catch (e) {
      console.error("Failed to load clinic details:", e);
    }
  }, [getCacheItem, setCacheItem]);

  // Fetch Appointments from API with filtering
  const fetchAppointments = useCallback(async (tab, bypassCache = false) => {
    const cacheKey = `appointments:${tab}`;
    const cached = bypassCache ? null : getCacheItem(cacheKey);
    if (cached) {
      setAppointments(cached);
      setLoading(false);
    } else {
      setLoading(true);
    }

    try {
      const now = new Date();
      let url = "/appointments";
      const params = new URLSearchParams();
      params.append("limit", "200");

      if (viewMode === "calendar" || tab === "all") {
        // Fetch all appointments for full month calendar visibility
      } else if (tab === "today") {
        params.append("date_from", startOfDay(now).toISOString());
        params.append("date_to", endOfDay(now).toISOString());
      } else if (tab === "upcoming") {
        params.append("date_from", now.toISOString());
        params.append("date_to", endOfDay(addDays(now, 7)).toISOString());
      }

      const res = await api.get(`${url}?${params.toString()}`);
      const data = res.data.data || [];
      setAppointments(data);
      setCacheItem(cacheKey, data);
    } catch (err) {
      console.error("Failed to fetch appointments", err);
    } finally {
      setLoading(false);
    }
  }, [getCacheItem, setCacheItem, viewMode]);

  useEffect(() => {
    fetchAppointments(viewMode === "calendar" ? "all" : activeDateTab);
    fetchClinicStatus();
  }, [activeDateTab, viewMode, fetchAppointments, fetchClinicStatus]);

  // WebSocket Live Events Listener
  useEffect(() => {
    if (!lastEvent) return;
    const { event, data } = lastEvent;

    if (event === "APPOINTMENT_ADDED" || event === "APPOINTMENT_CREATED") {
      const patientName = data?.patient_name || data?.appointment?.patient_name || "Patient";
      showToast(`⚡ Real-time: New appointment booked for ${patientName}!`, "success");
      setCacheItem("appointments:today", null);
      setCacheItem("appointments:upcoming", null);
      setCacheItem("appointments:all", null);
      fetchAppointments(activeDateTab, true);
    } else if (event === "APPOINTMENT_CANCELLED") {
      const patientName = data?.patient_name || "Patient";
      showToast(`⚡ Real-time: Appointment cancelled for ${patientName}. Waitlist triggered!`, "warning");
      setCacheItem("appointments:today", null);
      setCacheItem("appointments:upcoming", null);
      setCacheItem("appointments:all", null);
      fetchAppointments(activeDateTab, true);
    } else if (event === "APPOINTMENT_UPDATED" || event === "OUTBOUND_CALL_COMPLETED" || event === "outbound_call_completed") {
      if (data?.status === "confirmed") {
        showToast(`⚡ Real-time: Appointment confirmed via CALL-E!`, "success");
      }
      setCacheItem("appointments:today", null);
      setCacheItem("appointments:upcoming", null);
      setCacheItem("appointments:all", null);
      fetchAppointments(activeDateTab, true);
    }
  }, [lastEvent, activeDateTab, fetchAppointments, setCacheItem, showToast]);

  // Actions
  const updateStatus = async (apptId, status) => {
    setUpdatingId(apptId);
    try {
      await api.put(`/appointments/${apptId}`, { status });
      setAppointments((prev) => {
        const next = prev.map((a) => (a.id === apptId ? { ...a, status } : a));
        setCacheItem(`appointments:${activeDateTab}`, next);
        return next;
      });
      if (selectedAppt?.id === apptId) setSelectedAppt((a) => ({ ...a, status }));
      showToast(`Appointment status updated to ${status.replace("_", " ")}!`);
    } catch (err) {
      console.error("Failed to update status", err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to update status";
      showToast(errMsg, "error");
    } finally {
      setUpdatingId(null);
    }
  };

  const updateInsurance = async (apptId, verified) => {
    try {
      await api.put(`/appointments/${apptId}`, { insurance_verified: verified });
      setAppointments((prev) => {
        const next = prev.map((a) => (a.id === apptId ? { ...a, insurance_verified: verified } : a));
        setCacheItem(`appointments:${activeDateTab}`, next);
        return next;
      });
      if (selectedAppt?.id === apptId) setSelectedAppt((a) => ({ ...a, insurance_verified: verified }));
      showToast("Insurance verification status updated!");
    } catch (err) {
      console.error("Failed to update insurance status", err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to update insurance status";
      showToast(errMsg, "error");
    }
  };

  const updateNotes = async (apptId, notes) => {
    try {
      await api.put(`/appointments/${apptId}`, { notes });
      setAppointments((prev) => {
        const next = prev.map((a) => (a.id === apptId ? { ...a, notes } : a));
        setCacheItem(`appointments:${activeDateTab}`, next);
        return next;
      });
      if (selectedAppt?.id === apptId) setSelectedAppt((a) => ({ ...a, notes }));
      showToast("Notes saved successfully!");
    } catch (err) {
      console.error("Failed to update notes", err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to update notes";
      showToast(errMsg, "error");
    }
  };

  const triggerConfirmationCall = async (appt) => {
    if (!appt || !appt.patient_phone) {
      showToast("No patient contact phone registered for this appointment.", "error");
      return;
    }
    setIsTriggeringCall(true);
    try {
      const timeStr = appt.datetime ? fmtClinicTime(appt.datetime, timezone) : "your scheduled time";
      const res = await api.post("/calle/calls/single", {
        phone: appt.patient_phone,
        campaign_type: "confirmation",
        appointment_id: appt.id,
        patient_name: appt.patient_name || "Patient",
        time_str: timeStr,
        clinic_name: clinic?.name || "Medical Clinic",
        wait_for_completion: false
      });
      showToast(`🤖 CALL-E 24h confirmation voice call initiated for ${appt.patient_name || 'Patient'}!`, "success");
    } catch (err) {
      console.error("Failed to initiate confirmation call:", err);
      const errMsg = err.response?.data?.detail || err.message || "Failed to initiate confirmation call.";
      showToast(`Call error: ${errMsg}`, "error");
    } finally {
      setIsTriggeringCall(false);
    }
  };


  const selectAppt = async (apt) => {
    if (selectedAppt?.id === apt.id) {
      setSelectedAppt(null);
      setApptCall(null);
      setApptPatient(null);
      return;
    }
    setSelectedAppt(apt);
    setApptCall(null);
    setApptPatient(null);
    setCallLoading(true);
    setPatientLoading(true);

    try {
      const res = await api.get(`/calls?appointment_id=${apt.id}&limit=1`);
      const calls = res.data.data || [];
      if (calls.length === 0 && apt.patient_phone) {
        const res2 = await api.get(`/calls?from_number=${encodeURIComponent(apt.patient_phone)}&limit=5`);
        const calls2 = res2.data.data || [];
        setApptCall(calls2[0] || null);
      } else {
        setApptCall(calls[0] || null);
      }
    } catch (err) {
      console.error("Failed to fetch call transcript", err);
      setApptCall(null);
    } finally {
      setCallLoading(false);
    }

    try {
      if (apt.patient_id) {
        const pRes = await api.get(`/patients/${apt.patient_id}`);
        setApptPatient(pRes.data.data || null);
      } else if (apt.patient_phone) {
        const pRes = await api.get(`/patients?search=${encodeURIComponent(apt.patient_phone)}&limit=1`);
        const pList = pRes.data.data || [];
        if (pList.length > 0) {
          const pRes2 = await api.get(`/patients/${pList[0].id}`);
          setApptPatient(pRes2.data.data || null);
        }
      }
    } catch (err) {
      console.error("Failed to fetch patient details", err);
      setApptPatient(null);
    } finally {
      setPatientLoading(false);
    }
  };

  const handlePrevMonth = () => {
    setCurrentMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() - 1, 1));
  };

  const handleNextMonth = () => {
    setCurrentMonthDate((prev) => new Date(prev.getFullYear(), prev.getMonth() + 1, 1));
  };

  const clinicTz = clinic?.timezone || DEFAULT_TZ;

  // Filter and conflict processing
  const filteredAppointments = useMemo(() => {
    return appointments.filter((apt) => {
      // Doctor filter
      if (selectedDoctor !== "all") {
        const doctorMatch =
          apt.doctor_name === selectedDoctor ||
          (apt.provider && apt.provider.display_name === selectedDoctor);
        if (!doctorMatch) return false;
      }

      // Status filter
      if (selectedStatus !== "all") {
        if (apt.status !== selectedStatus) return false;
      }

      // Search query (name, phone, service type)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const nameMatch = (apt.patient_name || apt.patient?.full_name || "").toLowerCase().includes(q);
        const phoneMatch = (apt.patient_phone || apt.patient?.phone || "").toLowerCase().includes(q);
        const serviceMatch = (apt.appointment_type || apt.service_type || "").toLowerCase().includes(q);
        if (!nameMatch && !phoneMatch && !serviceMatch) return false;
      }

      return true;
    });
  }, [appointments, selectedDoctor, selectedStatus, searchQuery]);

  const appointmentsWithConflicts = useMemo(() => {
    return filteredAppointments.map((apt) => {
      if (apt.status === "cancelled") return { ...apt, conflict: null };

      const start = new Date(apt.datetime).getTime();
      const end = start + Number(apt.duration_minutes || 30) * 60 * 1000;

      const conflictingApt = filteredAppointments.find((other) => {
        if (other.id === apt.id || other.status === "cancelled") return false;
        const otherStart = new Date(other.datetime).getTime();
        const otherEnd = otherStart + Number(other.duration_minutes || 30) * 60 * 1000;
        return start < otherEnd && otherStart < end;
      });

      return { ...apt, conflict: conflictingApt || null };
    });
  }, [filteredAppointments]);

  const grouped = useMemo(() => {
    return appointmentsWithConflicts.reduce((acc, appt) => {
      const d = new Date(appt.datetime);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      if (!acc[key]) acc[key] = [];
      acc[key].push(appt);
      return acc;
    }, {});
  }, [appointmentsWithConflicts]);

  // Metric counts
  const stats = useMemo(() => {
    const total = appointments.length;
    const confirmed = appointments.filter((a) => a.status === "confirmed").length;
    const scheduled = appointments.filter((a) => a.status === "scheduled").length;
    const cancelled = appointments.filter((a) => a.status === "cancelled" || a.status === "no_show").length;
    return { total, confirmed, scheduled, cancelled };
  }, [appointments]);

  const getDaysInMonth = (year, month) => new Date(year, month + 1, 0).getDate();
  const getFirstDayOfMonth = (year, month) => new Date(year, month, 1).getDay();
  const getCellDateKey = (dateObj) => {
    const y = dateObj.getFullYear();
    const m = String(dateObj.getMonth() + 1).padStart(2, "0");
    const d = String(dateObj.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };

  const renderCalendarView = () => {
    const year = currentMonthDate.getFullYear();
    const month = currentMonthDate.getMonth();

    const daysInMonth = getDaysInMonth(year, month);
    const firstDayIndex = getFirstDayOfMonth(year, month);

    const prevMonthDate = new Date(year, month - 1, 1);
    const prevMonthDays = getDaysInMonth(prevMonthDate.getFullYear(), prevMonthDate.getMonth());

    const calendarCells = [];

    for (let i = firstDayIndex - 1; i >= 0; i--) {
      calendarCells.push({
        date: new Date(year, month - 1, prevMonthDays - i),
        isCurrentMonth: false,
      });
    }

    for (let i = 1; i <= daysInMonth; i++) {
      calendarCells.push({
        date: new Date(year, month, i),
        isCurrentMonth: true,
      });
    }

    const remainingCells = 42 - calendarCells.length;
    for (let i = 1; i <= remainingCells; i++) {
      calendarCells.push({
        date: new Date(year, month + 1, i),
        isCurrentMonth: false,
      });
    }

    return (
      <div className="p-4 flex flex-col h-full min-h-[520px] bg-white">
        {/* Weekday labels */}
        <div className="grid grid-cols-7 gap-px border-b border-[#edf1ef] pb-3 text-center text-[10px] font-bold text-slate-400 uppercase tracking-widest">
          <div>Sun</div>
          <div>Mon</div>
          <div>Tue</div>
          <div>Wed</div>
          <div>Thu</div>
          <div>Fri</div>
          <div>Sat</div>
        </div>

        {/* Days grid */}
        <div className="grid grid-cols-7 grid-rows-6 gap-px bg-[#edf1ef] flex-1 mt-2.5 rounded-2xl overflow-hidden border border-[#edf1ef]">
          {calendarCells.map((cell, index) => {
            const keyStr = getCellDateKey(cell.date);
            const cellAppts = grouped[keyStr] || [];
            const sortedAppts = [...cellAppts].sort((a, b) => a.datetime.localeCompare(b.datetime));
            const isTodayCell = isToday(cell.date);

            return (
              <div
                key={index}
                className={`p-2 flex flex-col justify-between transition-all relative group min-h-[90px] ${
                  cell.isCurrentMonth ? "bg-white" : "bg-[#f7faf9]/40 opacity-40"
                } ${isTodayCell ? "bg-[#7FCD4D]/10 ring-1 ring-[#7FCD4D]/30" : "border-[#edf1ef]"}`}
              >
                <div className="flex justify-between items-center mb-1">
                  <span
                    className={`text-[10px] font-extrabold ${
                      isTodayCell
                        ? "w-5 h-5 rounded-md bg-[#396a00] text-white flex items-center justify-center shadow-sm font-sans"
                        : "text-on-surface-variant"
                    }`}
                  >
                    {cell.date.getDate()}
                  </span>

                  {cell.isCurrentMonth && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        const y = cell.date.getFullYear();
                        const m = String(cell.date.getMonth() + 1).padStart(2, "0");
                        const d = String(cell.date.getDate()).padStart(2, "0");
                        setPrefilledDate(`${y}-${m}-${d}`);
                        setShowNewModal(true);
                      }}
                      className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-slate-100 text-[#396a00] transition-all border-none bg-transparent cursor-pointer"
                      title="Schedule Appointment"
                    >
                      <Plus className="w-3.5 h-3.5 text-[#396a00]" />
                    </button>
                  )}
                </div>

                {/* Badges */}
                <div className="flex-1 space-y-1 overflow-y-auto no-scrollbar max-h-[75px] mt-1">
                  {sortedAppts.slice(0, 3).map((appt) => {
                    const cfg = STATUS_CFG[appt.status] || STATUS_CFG.scheduled;
                    const isSelected = selectedAppt?.id === appt.id;
                    const isBlocked = (appt.patient_name || "").startsWith("[BLOCKED]");

                    return (
                      <div
                        key={appt.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          selectAppt(appt);
                        }}
                        className={`text-[9px] leading-tight px-1.5 py-0.5 rounded-md font-bold truncate cursor-pointer transition-all border border-solid ${
                          isSelected
                            ? "bg-[#edf7e0] border-[#396a00] text-[#396a00]"
                            : appt.conflict
                            ? "bg-amber-50 hover:bg-amber-100 border-amber-300 text-amber-900"
                            : "bg-slate-50 hover:bg-slate-100 border-[#bec9c4]/30 text-on-surface-variant"
                        }`}
                        style={{
                          borderLeftWidth: "3px",
                          borderLeftColor: appt.conflict ? "#d97706" : cfg.dotColor,
                        }}
                        title={`${fmtClinicTime(appt.datetime, clinicTz)} - ${appt.patient_name} (${appt.doctor_name || "Doctor"})${
                          appt.conflict ? ` (Conflict: Overlaps with ${appt.conflict.patient_name})` : ""
                        }`}
                      >
                        <span className="font-extrabold mr-1 font-mono">
                          {fmtClinicTime(appt.datetime, clinicTz).split(" ")[0]}
                        </span>
                        <span>{isBlocked ? "Busy Block" : appt.patient_name}</span>
                        {appt.doctor_name && (
                          <span className="text-[8px] text-[#396a00] ml-1 opacity-80">
                            • {appt.doctor_name.split(" ")[1] || appt.doctor_name}
                          </span>
                        )}
                      </div>
                    );
                  })}
                  {sortedAppts.length > 3 && (
                    <div
                      onClick={(e) => {
                        e.stopPropagation();
                        setViewMode("list");
                        setActiveDateTab("all");
                      }}
                      className="text-[8px] text-center text-[#396a00] font-bold hover:underline cursor-pointer py-0.5 bg-[#7FCD4D]/10 rounded-md"
                    >
                      +{sortedAppts.length - 3} more
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col gap-4 pb-8 min-h-[calc(100vh-56px)]">
      {/* Header with Title & KPI Bar */}
      <div className="flex items-start justify-between flex-wrap gap-4 flex-shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="page-header-title">
              {t.appointments_title || "Appointments & Calendar"}
            </h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                isConnected
                  ? "bg-emerald-500/10 text-emerald-600 border-emerald-500/20"
                  : "bg-amber-500/10 text-amber-600 border-amber-500/20"
              }`}
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"
                }`}
              />
              {isConnected ? "Live CALL-E Sync" : "Connecting..."}
            </span>
          </div>
          <p className="page-header-sub">
            {t.appointments_sub ||
              "Multi-doctor scheduling, real-time slot conflict locking, and automated 24h voice confirmations."}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchAppointments(activeDateTab, true)}
            className="p-2.5 border border-[#bec9c4]/60 hover:bg-slate-100 rounded-xl text-slate-700 bg-white transition-all cursor-pointer shadow-sm"
            title="Refresh Appointments"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setPrefilledDate("");
              setShowNewModal(true);
            }}
            className="btn-primary flex items-center gap-2 border-none cursor-pointer text-xs py-2.5 px-4 font-bold shadow-md shadow-[#396a00]/20"
          >
            <Plus className="w-4 h-4" />
            {t.new_appointment || "New Appointment"}
          </button>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-[#edf1ef] rounded-2xl p-3.5 shadow-sm">
          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Total Booked</p>
          <p className="text-xl font-extrabold text-[#181c1c] mt-0.5 font-mono">{stats.total}</p>
        </div>
        <div className="bg-white border border-[#edf1ef] rounded-2xl p-3.5 shadow-sm">
          <p className="text-[10px] font-bold text-emerald-700 uppercase tracking-widest">Confirmed</p>
          <p className="text-xl font-extrabold text-[#396a00] mt-0.5 font-mono">{stats.confirmed}</p>
        </div>
        <div className="bg-white border border-[#edf1ef] rounded-2xl p-3.5 shadow-sm">
          <p className="text-[10px] font-bold text-sky-700 uppercase tracking-widest">Pending / Scheduled</p>
          <p className="text-xl font-extrabold text-sky-600 mt-0.5 font-mono">{stats.scheduled}</p>
        </div>
        <div className="bg-white border border-[#edf1ef] rounded-2xl p-3.5 shadow-sm">
          <p className="text-[10px] font-bold text-rose-700 uppercase tracking-widest">Cancelled / No-Show</p>
          <p className="text-xl font-extrabold text-rose-600 mt-0.5 font-mono">{stats.cancelled}</p>
        </div>
      </div>

      {/* Filter Control Bar */}
      <div className="bg-white border border-[#edf1ef] rounded-2xl p-3 shadow-sm flex flex-wrap items-center justify-between gap-3">
        {/* Left: Date tabs & Doctor selector */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="flex bg-slate-100 p-1 rounded-xl gap-0.5 border border-slate-200/50">
            {[
              { key: "today", label: "Today" },
              { key: "upcoming", label: "Next 7 Days" },
              { key: "all", label: "All Dates" },
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveDateTab(tab.key)}
                className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all border-none cursor-pointer ${
                  activeDateTab === tab.key
                    ? "bg-white shadow text-[#396a00]"
                    : "text-on-surface-variant hover:text-[#181c1c] bg-transparent"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Doctor filter dropdown */}
          <div className="relative flex items-center">
            <Stethoscope className="w-3.5 h-3.5 text-[#396a00] absolute left-2.5 pointer-events-none" />
            <select
              value={selectedDoctor}
              onChange={(e) => setSelectedDoctor(e.target.value)}
              className="bg-slate-50 border border-slate-200 focus:border-[#396a00] rounded-xl pl-8 pr-3 py-1.5 text-xs font-bold text-[#181c1c] outline-none cursor-pointer hover:bg-slate-100 transition-all appearance-none"
            >
              <option value="all">All Doctors</option>
              {doctorsList.map((d) => (
                <option key={d.id} value={d.name}>
                  {d.name}
                </option>
              ))}
            </select>
          </div>

          {/* Status filter dropdown */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="bg-slate-50 border border-slate-200 focus:border-[#396a00] rounded-xl px-3 py-1.5 text-xs font-bold text-[#181c1c] outline-none cursor-pointer hover:bg-slate-100 transition-all"
          >
            <option value="all">All Statuses</option>
            <option value="scheduled">Scheduled</option>
            <option value="confirmed">Confirmed</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No-Show</option>
          </select>
        </div>

        {/* Right: Search Box & View Mode switcher */}
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-60">
            <input
              type="text"
              placeholder="Search patient, phone, service..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] rounded-xl pl-8 pr-7 py-1.5 text-xs font-semibold text-[#181c1c] outline-none transition-all"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2" />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-2 text-slate-400 hover:text-slate-700 border-none bg-transparent cursor-pointer p-0"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="flex bg-slate-100 p-1 rounded-xl gap-0.5 border border-slate-200/50 flex-shrink-0">
            <button
              type="button"
              onClick={() => setViewMode("calendar")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all border-none cursor-pointer ${
                viewMode === "calendar"
                  ? "bg-white shadow text-[#396a00]"
                  : "text-on-surface-variant hover:text-[#181c1c] bg-transparent"
              }`}
            >
              Calendar
            </button>
            <button
              type="button"
              onClick={() => setViewMode("list")}
              className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all border-none cursor-pointer ${
                viewMode === "list"
                  ? "bg-white shadow text-[#396a00]"
                  : "text-on-surface-variant hover:text-[#181c1c] bg-transparent"
              }`}
            >
              List
            </button>
          </div>
        </div>
      </div>

      {/* Main Split Panel Content */}
      <div className="flex flex-col lg:flex-row gap-5 flex-1 min-h-0 pb-10 lg:pb-0 overflow-y-auto lg:overflow-hidden">
        {/* Left Container */}
        <div
          className={`flex-[3] flex-col bg-white border border-[#edf1ef] rounded-2xl overflow-hidden min-h-[450px] lg:min-h-0 ${
            selectedAppt ? "hidden lg:flex" : "flex"
          }`}
        >
          {/* Calendar Month Navigation Header (only in calendar mode) */}
          {viewMode === "calendar" && (
            <div className="px-4 py-3 border-b border-[#edf1ef] flex items-center justify-between bg-white flex-shrink-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-black text-[#181c1c] uppercase tracking-wider font-sans">
                  {currentMonthDate.toLocaleDateString("en-US", { month: "long", year: "numeric" })}
                </span>
                <span className="text-[10px] font-bold text-slate-400">({clinicTz})</span>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={handlePrevMonth}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-[#bec9c4]/60 hover:bg-slate-100 text-slate-700 bg-white transition-colors cursor-pointer"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => setCurrentMonthDate(new Date())}
                  className="px-2.5 py-1 text-[10px] font-bold rounded-lg border border-[#bec9c4]/60 hover:bg-slate-100 text-slate-700 bg-white transition-colors cursor-pointer"
                >
                  Today
                </button>
                <button
                  type="button"
                  onClick={handleNextMonth}
                  className="w-7 h-7 flex items-center justify-center rounded-lg border border-[#bec9c4]/60 hover:bg-slate-100 text-slate-700 bg-white transition-colors cursor-pointer"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}

          {/* Body: Calendar or List Table */}
          <div className="flex-1 overflow-auto thin-scrollbar">
            {loading ? (
              <div className="p-5 space-y-3 bg-white">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-16 bg-slate-50 border border-slate-100 rounded-xl animate-pulse" />
                ))}
              </div>
            ) : viewMode === "calendar" ? (
              renderCalendarView()
            ) : filteredAppointments.length === 0 ? (
              <div className="py-20 text-center bg-white flex flex-col items-center justify-center">
                <div className="w-14 h-14 bg-slate-50 border border-slate-100 rounded-2xl flex items-center justify-center mb-4">
                  <CalendarDays className="w-6 h-6 text-slate-400" />
                </div>
                <p className="font-bold text-[#181c1c] text-sm">No appointments matching filters</p>
                <p className="text-[11px] text-on-surface-variant mt-1 max-w-[220px] leading-relaxed">
                  Try adjusting the date range, doctor, or status filter to see scheduled appointments.
                </p>
              </div>
            ) : (
              <div className="bg-white">
                {Object.entries(grouped)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([date, appts]) => (
                    <div key={date} className="border-b border-[#edf1ef] last:border-b-0 pb-4">
                      <p className="text-[9px] font-bold text-slate-400 uppercase tracking-widest px-5 pt-4 pb-2">
                        {appts[0]?.datetime ? fmtClinicDate(appts[0].datetime, clinicTz) : date}
                      </p>
                      <div className="overflow-x-auto">
                        <table className="w-full text-left min-w-[700px] border-collapse">
                          <thead>
                            <tr>
                              <th className="table-header-cell">Patient</th>
                              <th className="table-header-cell">Doctor / Provider</th>
                              <th className="table-header-cell">Time</th>
                              <th className="table-header-cell">Service</th>
                              <th className="table-header-cell">Eligibility</th>
                              <th className="table-header-cell">Status</th>
                              <th className="table-header-cell">Actions</th>
                            </tr>
                          </thead>
                          <tbody>
                            {appts.map((apt) => {
                              const isSelected = selectedAppt?.id === apt.id;
                              const isBlocked = (apt.patient_name || "").startsWith("[BLOCKED]");

                              return (
                                <tr
                                  key={apt.id}
                                  onClick={() => selectAppt(apt)}
                                  className={`table-row ${isSelected ? "selected" : ""}`}
                                >
                                  {/* Patient */}
                                  <td className="table-cell">
                                    <div className="flex items-center gap-3">
                                      {isBlocked ? (
                                        <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 flex-shrink-0 border border-slate-200">
                                          <Clock className="w-4 h-4 text-slate-500" />
                                        </div>
                                      ) : (
                                        <div
                                          className="w-9 h-9 rounded-lg flex items-center justify-center text-[10px] font-extrabold flex-shrink-0 text-[#181c1c] border border-solid border-white/50"
                                          style={{ backgroundColor: avatarColor(apt.patient_name) }}
                                        >
                                          {initials(apt.patient_name)}
                                        </div>
                                      )}
                                      <div>
                                        <div className="flex items-center gap-2 flex-wrap">
                                          <p
                                            className={`font-semibold text-sm text-[#181c1c] ${
                                              isBlocked ? "text-[#585d77] italic" : ""
                                            }`}
                                          >
                                            {isBlocked
                                              ? apt.patient_name.replace("[BLOCKED] ", "")
                                              : apt.patient_name}
                                          </p>
                                          {isBlocked && (
                                            <span className="text-[0.55rem] font-bold px-1.5 py-0.5 rounded-md bg-slate-200 text-slate-700 border border-slate-300">
                                              BLOCKED
                                            </span>
                                          )}
                                          {apt.noshow_risk >= 0.5 && !isBlocked && (
                                            <span className="text-[0.55rem] font-bold px-1.5 py-0.5 rounded-md bg-red-100 text-red-800 animate-pulse">
                                              HIGH RISK
                                            </span>
                                          )}
                                        </div>
                                        {apt.conflict && (
                                          <div className="mt-1 flex items-center gap-1 text-[10px] text-amber-700 font-extrabold bg-amber-50 border border-amber-200/50 rounded px-1.5 py-0.5 w-max">
                                            <AlertCircle className="w-3.5 h-3.5 text-amber-500 animate-pulse" />
                                            <span>
                                              Conflict: Overlaps with {apt.conflict.patient_name} (
                                              {fmtClinicTime(apt.conflict.datetime, clinicTz)})
                                            </span>
                                          </div>
                                        )}
                                        <div className="flex items-center gap-1.5 mt-0.5">
                                          {isBlocked ? (
                                            <>
                                              <Sliders className="w-3 h-3 text-slate-400" />
                                              <span className="text-[0.65rem] text-slate-400 font-bold">
                                                Availability Block
                                              </span>
                                            </>
                                          ) : (
                                            <>
                                              {apt.booked_by === "ai" ? (
                                                <Bot className="w-3 h-3 text-[#396a00]" />
                                              ) : (
                                                <User className="w-3 h-3 text-[#006493]" />
                                              )}
                                              <span className="text-[0.65rem] text-on-surface-variant font-bold">
                                                {apt.booked_by === "ai" ? "CALL-E Voice" : "Clinic Staff"}
                                              </span>
                                            </>
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  </td>

                                  {/* Doctor */}
                                  <td className="table-cell">
                                    <div className="flex items-center gap-2">
                                      <div className="w-6 h-6 rounded-md bg-emerald-50 text-[#396a00] flex items-center justify-center font-bold text-[10px]">
                                        <Stethoscope className="w-3.5 h-3.5" />
                                      </div>
                                      <div>
                                        <p className="font-bold text-xs text-[#181c1c]">
                                          {apt.doctor_name || apt.provider?.display_name || "Dr. Sarah Jenkins"}
                                        </p>
                                        <p className="text-[9px] text-on-surface-variant font-medium">
                                          {apt.provider?.specialty || "Physician"}
                                        </p>
                                      </div>
                                    </div>
                                  </td>

                                  {/* Time */}
                                  <td className="table-cell">
                                    <p className="font-extrabold text-[#181c1c] text-sm font-mono">
                                      {fmtClinicTime(apt.datetime, clinicTz)}
                                    </p>
                                    <p className="text-[10px] text-on-surface-variant font-semibold mt-0.5">
                                      {apt.duration_minutes || 30} min · {getTzAbbr(apt.datetime, clinicTz)}
                                    </p>
                                  </td>

                                  {/* Service */}
                                  <td className="table-cell text-sm text-[#181c1c] font-medium">
                                    {apt.appointment_type || apt.service_type || "Consultation"}
                                  </td>

                                  {/* Eligibility */}
                                  <td className="table-cell">
                                    <EligibilityBadge
                                      status={apt.eligibility_status || "unverified"}
                                      priorAuth={apt.prior_auth_required}
                                      small
                                    />
                                  </td>

                                  {/* Status */}
                                  <td className="table-cell">
                                    <StatusBadge status={apt.status} />
                                  </td>

                                  {/* Action Buttons */}
                                  <td className="table-cell" onClick={(e) => e.stopPropagation()}>
                                    <div className="flex items-center gap-1.5">
                                      {apt.status === "scheduled" && (
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            updateStatus(apt.id, "confirmed");
                                          }}
                                          disabled={updatingId === apt.id}
                                          className="flex items-center gap-1 px-2.5 py-1 text-[0.65rem] font-bold rounded-md border-none cursor-pointer transition-colors disabled:opacity-40"
                                          style={{ backgroundColor: "#edf7e0", color: "#396a00" }}
                                        >
                                          <CheckCircle className="w-3 h-3" /> Confirm
                                        </button>
                                      )}
                                      {(apt.status === "scheduled" || apt.status === "confirmed") && (
                                        <>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              updateStatus(apt.id, "no_show");
                                            }}
                                            disabled={updatingId === apt.id}
                                            className="flex items-center gap-1 px-2.5 py-1 text-[0.65rem] font-bold rounded-md border-none cursor-pointer transition-colors disabled:opacity-40"
                                            style={{ backgroundColor: "#fff8e1", color: "#9a6800" }}
                                          >
                                            <AlertCircle className="w-3 h-3" /> No-Show
                                          </button>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              updateStatus(apt.id, "cancelled");
                                            }}
                                            disabled={updatingId === apt.id}
                                            className="flex items-center gap-1 px-2.5 py-1 text-[0.65rem] font-bold rounded-md border-none cursor-pointer transition-colors disabled:opacity-40"
                                            style={{ backgroundColor: "#fce4ec", color: "#b71c1c" }}
                                          >
                                            <XCircle className="w-3 h-3" /> Cancel
                                          </button>
                                        </>
                                      )}
                                      {apt.status === "confirmed" && (
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            updateStatus(apt.id, "completed");
                                          }}
                                          disabled={updatingId === apt.id}
                                          className="flex items-center gap-1 px-2.5 py-1 text-[0.65rem] font-bold rounded-md border-none cursor-pointer transition-colors disabled:opacity-40"
                                          style={{ backgroundColor: "#ede7f6", color: "#4a148c" }}
                                        >
                                          <CheckCircle className="w-3 h-3" /> Complete
                                        </button>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Drawer Detailed Panel */}
        <div
          className={`flex-[2] flex-col bg-white border border-[#edf1ef] rounded-2xl overflow-hidden min-h-[450px] lg:min-h-0 ${
            !selectedAppt ? "hidden lg:flex" : "flex"
          }`}
        >
          <AppointmentDetailPanel
            appointment={selectedAppt}
            call={apptCall}
            patient={apptPatient}
            loadingCall={callLoading}
            loadingPatient={patientLoading}
            onClose={() => {
              setSelectedAppt(null);
              setApptCall(null);
              setApptPatient(null);
            }}
            onUpdateStatus={updateStatus}
            onUpdateInsurance={updateInsurance}
            onUpdateNotes={updateNotes}
            onTriggerConfirmationCall={triggerConfirmationCall}
            onMaximize={() => setShowDetailModal(true)}
            updatingId={updatingId}
            isTriggeringCall={isTriggeringCall}
            timezone={clinicTz}
          />
        </div>
      </div>

      {/* Appointment Modal */}
      {showNewModal && (
        <AppointmentModal
          isOpen={showNewModal}
          timezone={clinicTz}
          initialDate={prefilledDate}
          existingAppointments={appointments}
          appointmentTypes={clinic?.appointment_types}
          doctors={doctorsList}
          onClose={() => {
            setShowNewModal(false);
            setPrefilledDate("");
          }}
          onCreated={() => {
            showToast("Appointment booked successfully! Instant SMS and CALL-E queued.");
            fetchAppointments(activeDateTab, true);
          }}
        />
      )}

      {/* Full Screen Clinical Modal */}
      {showDetailModal && selectedAppt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm p-4">
          <div className="bg-white border border-[#edf1ef] w-full max-w-5xl p-6 h-[85vh] flex flex-col rounded-3xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#edf1ef] pb-4 mb-4 flex-shrink-0">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[0.6rem] font-black tracking-widest text-[#396a00] uppercase bg-[#7FCD4D]/15 px-2 py-0.5 rounded-md">
                    CLINICAL PROFILE SUMMARY
                  </span>
                  <span className="w-1.5 h-1.5 rounded-full bg-slate-200" />
                  {selectedAppt.noshow_risk >= 0.5 ? (
                    <span className="text-[0.6rem] font-bold px-2 py-0.5 rounded-md bg-red-100 text-red-800 animate-pulse">
                      🔴 DANGER: HIGH NO-SHOW RISK ({Math.round(selectedAppt.noshow_risk * 100)}%)
                    </span>
                  ) : (
                    <span className="text-[0.6rem] font-bold px-2 py-0.5 rounded-md bg-[#edf7e0] text-[#396a00]">
                      🟢 LOW NO-SHOW RISK ({Math.round((selectedAppt.noshow_risk || 0) * 100)}%)
                    </span>
                  )}
                </div>
                <h2 className="text-lg font-extrabold text-[#181c1c] truncate">
                  {selectedAppt.patient_name}
                </h2>
                <p className="text-xs text-on-surface-variant font-semibold mt-0.5">
                  {selectedAppt.appointment_type} · {fmtClinicDate(selectedAppt.datetime, clinicTz)} at{" "}
                  {fmtClinicTime(selectedAppt.datetime, clinicTz)}
                  {selectedAppt.doctor_name ? ` · ${selectedAppt.doctor_name}` : ""}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <select
                  value={selectedAppt.status}
                  onChange={(e) => updateStatus(selectedAppt.id, e.target.value)}
                  disabled={updatingId === selectedAppt.id}
                  className="text-xs font-semibold px-2 py-1.5 rounded-lg bg-slate-50 border border-[#bec9c4] outline-none cursor-pointer hover:bg-slate-100 transition-all font-sans"
                >
                  <option value="scheduled">Scheduled</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="completed">Completed</option>
                  <option value="cancelled">Cancelled</option>
                  <option value="no_show">No-Show</option>
                </select>

                <button
                  onClick={() => setShowDetailModal(false)}
                  className="p-1.5 text-slate-500 hover:bg-slate-100 rounded-full cursor-pointer border-none bg-transparent"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Conflict Banner */}
            {selectedAppt.conflict && (
              <div className="mb-4 p-3.5 bg-amber-50 border border-amber-200 rounded-xl flex gap-2.5 items-start text-xs text-amber-900 flex-shrink-0 select-none shadow-sm">
                <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5 animate-pulse" />
                <div>
                  <p className="font-bold text-amber-900">Active Scheduling Conflict</p>
                  <p className="opacity-90 mt-1 leading-relaxed">
                    This appointment overlaps with{" "}
                    <span className="font-bold">
                      {selectedAppt.conflict.patient_name.startsWith("[BLOCKED]")
                        ? selectedAppt.conflict.patient_name.replace("[BLOCKED] ", "")
                        : selectedAppt.conflict.patient_name}
                    </span>{" "}
                    ({fmtClinicTime(selectedAppt.conflict.datetime, clinicTz)}).
                  </p>
                </div>
              </div>
            )}

            {/* Modal Body Scroll grid */}
            <div className="flex-1 grid grid-cols-1 md:grid-cols-2 gap-6 min-h-0 overflow-y-auto pr-1">
              {/* Left Detail Elements */}
              <div className="space-y-4 overflow-y-auto pr-1 thin-scrollbar">
                <div className="bg-white border border-[#edf1ef] rounded-2xl p-4 shadow-sm">
                  <h3 className="text-[10px] font-bold text-[#396a00] mb-3 uppercase tracking-wider">
                    Demographics
                  </h3>
                  {patientLoading ? (
                    <div className="h-20 bg-slate-50 animate-pulse rounded-xl" />
                  ) : apptPatient ? (
                    <div className="grid grid-cols-2 gap-3 text-xs font-medium">
                      <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                        <p className="text-[8px] font-bold text-slate-400 uppercase">Phone Number</p>
                        <p className="text-xs text-[#181c1c] mt-0.5 font-mono">
                          {apptPatient.patient?.phone || "-"}
                        </p>
                      </div>
                      <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                        <p className="text-[8px] font-bold text-slate-400 uppercase">Email Address</p>
                        <p className="text-xs text-[#181c1c] mt-0.5 truncate">
                          {apptPatient.patient?.email || "-"}
                        </p>
                      </div>
                      <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                        <p className="text-[8px] font-bold text-slate-400 uppercase">Date of Birth</p>
                        <p className="text-xs text-[#181c1c] mt-0.5">
                          {apptPatient.patient?.date_of_birth
                            ? format(parseISO(apptPatient.patient.date_of_birth), "MMM d, yyyy")
                            : "-"}
                        </p>
                      </div>
                      <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                        <p className="text-[8px] font-bold text-slate-400 uppercase">Clinical History</p>
                        <p className="text-xs text-[#181c1c] mt-0.5">
                          {apptPatient.patient?.total_visits || 0} visits ·{" "}
                          {apptPatient.patient?.no_show_count || 0} no-shows
                        </p>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-on-surface-variant font-medium">No demographic data loaded.</p>
                  )}
                </div>

                <div className="bg-white border border-[#edf1ef] rounded-2xl p-4 shadow-sm">
                  <div className="flex justify-between items-center mb-3">
                    <h3 className="text-[10px] font-bold text-[#396a00] uppercase tracking-wider">
                      Insurance Details
                    </h3>
                    <button
                      onClick={() => updateInsurance(selectedAppt.id, !selectedAppt.insurance_verified)}
                      className={`flex items-center gap-1 px-3 py-1 text-[10px] font-bold rounded-md transition-all cursor-pointer border-none ${
                        selectedAppt.insurance_verified
                          ? "bg-[#edf7e0] text-[#396a00] hover:bg-[#e2f0d0]"
                          : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                      }`}
                    >
                      <Shield
                        className={`w-3 h-3 ${selectedAppt.insurance_verified ? "fill-current" : ""}`}
                      />
                      {selectedAppt.insurance_verified ? "Verified" : "Verify Insurance"}
                    </button>
                  </div>

                  {apptPatient?.patient?.insurance_provider ? (
                    <div className="grid grid-cols-2 gap-3 text-xs font-medium">
                      <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                        <p className="text-[8px] font-bold text-slate-400 uppercase">Insurance Provider</p>
                        <p className="text-xs text-[#181c1c] mt-0.5">
                          {apptPatient.patient.insurance_provider}
                        </p>
                      </div>
                      <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                        <p className="text-[8px] font-bold text-slate-400 uppercase">Member ID</p>
                        <p className="text-xs font-mono text-[#181c1c] mt-0.5">
                          {apptPatient.patient.insurance_member_id || "N/A"}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 text-center text-xs text-on-surface-variant font-medium">
                      No insurance provider registered for this patient.
                    </div>
                  )}
                </div>
              </div>

              {/* Right Detail Elements */}
              <div className="space-y-4 overflow-y-auto pr-1 thin-scrollbar flex flex-col">
                {callLoading ? (
                  <div className="h-40 bg-slate-50 animate-pulse rounded-2xl" />
                ) : apptCall ? (
                  <>
                    <div className="bg-white border border-[#edf1ef] rounded-2xl p-4 shadow-sm relative overflow-hidden">
                      <div className="flex items-center gap-2 mb-3">
                        <div className="w-6 h-6 rounded-lg bg-[#7FCD4D]/10 flex items-center justify-center">
                          <Sparkles className="w-3.5 h-3.5 text-[#396a00]" />
                        </div>
                        <span className="text-xs font-bold text-[#181c1c]">AI Conversation Insights</span>
                      </div>

                      <div className="grid grid-cols-2 gap-3 mb-3.5">
                        <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                          <p className="text-[8px] font-bold text-slate-400 uppercase">Call Intent</p>
                          <p className="text-xs font-bold text-[#181c1c] mt-0.5 capitalize">
                            {apptCall.call_type || "Booking"}
                          </p>
                        </div>
                        <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                          <p className="text-[8px] font-bold text-slate-400 uppercase">Sentiment</p>
                          <span className="inline-block mt-0.5 px-2 py-0.5 text-[9px] font-bold rounded-md bg-emerald-100 text-emerald-800 font-sans">
                            Positive
                          </span>
                        </div>
                      </div>

                      <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                        <p className="text-[9px] font-bold text-slate-400 uppercase mb-1">AI Conversation Brief</p>
                        <p className="text-xs text-[#3d4946] leading-relaxed font-medium">
                          {apptCall.transcript
                            ? apptCall.transcript.slice(0, 300) +
                              (apptCall.transcript.length > 300 ? "..." : "")
                            : "No transcript summary parsed. Patient booked appointment via phone call."}
                        </p>
                      </div>
                    </div>

                    {apptCall.recording_url && (
                      <div className="space-y-1.5">
                        <label className="text-[9px] font-bold text-slate-400 uppercase tracking-widest block">
                          CALL RECORDING
                        </label>
                        <CustomAudioPlayer src={apptCall.recording_url} />
                      </div>
                    )}
                  </>
                ) : (
                  <div className="py-12 text-center bg-slate-50 border border-dashed border-slate-200 rounded-2xl flex flex-col items-center justify-center flex-1">
                    <Bot className="w-8 h-8 text-slate-300 mb-2" />
                    <p className="text-xs font-bold text-[#181c1c]">No Call Record Found</p>
                    <p className="text-[10px] text-[#181c1c] mt-1 max-w-[200px] mx-auto leading-relaxed">
                      This appointment was created manually by staff and does not have an AI call record.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Alert */}
      {toast && (
        <div
          className="fixed bottom-6 right-6 px-4 py-3 rounded-2xl shadow-xl border border-white/20 flex items-center gap-2 pointer-events-auto z-50 font-bold text-xs animate-in slide-in-from-bottom-5"
          style={{
            background: toast.type === "error" ? "#ef4444" : toast.type === "warning" ? "#f59e0b" : "#396a00",
            color: "white",
          }}
        >
          {toast.type === "error" ? (
            <XCircle size={16} />
          ) : toast.type === "warning" ? (
            <AlertCircle size={16} />
          ) : (
            <CheckCircle size={16} />
          )}
          {toast.msg}
        </div>
      )}
    </div>
  );
};

export default Appointments;
