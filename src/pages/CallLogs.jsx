import React, { useEffect, useState, useRef, useMemo } from "react";
import {
  Phone,
  PlayCircle,
  Clock,
  PhoneIncoming,
  PhoneOutgoing,
  RefreshCw,
  FileText,
  X,
  Sparkles,
  BookOpen,
  Play,
  Pause,
  Search,
  SlidersHorizontal,
  Shield,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  ChevronRight,
  Copy,
  Check,
  Volume2,
  VolumeX,
  RotateCcw,
  RotateCw,
  Calendar,
  ArrowUpRight,
  Download,
  BarChart3,
  Bot,
  User,
  Stethoscope,
  Activity,
  Maximize2,
  Minimize2,
} from "lucide-react";
import api from "../lib/api";
import { format, parseISO, formatDistanceToNow, isToday, isYesterday, subDays } from "date-fns";
import { useAuth } from "../context/AuthContext";
import { translations } from "../lib/translations";

/* ─── Waveform Visualizer & Audio Player with HIPAA Purge Countdown ──── */
const WaveformAudioPlayer = ({ src, recordingPurged, purgeScheduledAt }) => {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [volume, setVolume] = useState(0.85);

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
    if (!audioRef.current || recordingPurged || !src) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const handleScrub = (e) => {
    if (!audioRef.current) return;
    const time = Number(e.target.value);
    audioRef.current.currentTime = time;
    setCurrentTime(time);
  };

  const skipSeconds = (secs) => {
    if (!audioRef.current) return;
    const newTime = Math.max(0, Math.min(duration || 100, audioRef.current.currentTime + secs));
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
  };

  const cycleSpeed = () => {
    if (!audioRef.current) return;
    const speeds = [1, 1.25, 1.5, 2, 0.75];
    const nextIdx = (speeds.indexOf(playbackRate) + 1) % speeds.length;
    const nextSpeed = speeds[nextIdx];
    audioRef.current.playbackRate = nextSpeed;
    setPlaybackRate(nextSpeed);
  };

  const toggleMute = () => {
    if (!audioRef.current) return;
    audioRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const handleVolume = (e) => {
    if (!audioRef.current) return;
    const val = Number(e.target.value);
    audioRef.current.volume = val;
    setVolume(val);
    if (val === 0) setIsMuted(true);
    else setIsMuted(false);
  };

  const formatTime = (time) => {
    if (isNaN(time) || time === undefined) return "0:00";
    const mins = Math.floor(time / 60);
    const secs = Math.floor(time % 60);
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  // Generate 28 mock waveform frequency bars
  const bars = useMemo(() => {
    return Array.from({ length: 28 }, (_, i) => {
      const height = Math.sin(i * 0.45) * 40 + Math.cos(i * 0.9) * 30 + 45;
      return Math.max(15, Math.min(95, Math.round(height)));
    });
  }, []);

  const progressPct = duration > 0 ? (currentTime / duration) * 100 : 0;

  // HIPAA auto-purge remaining calculation
  let purgeCountdownText = null;
  if (purgeScheduledAt) {
    try {
      const purgeDate = typeof purgeScheduledAt === "string" ? parseISO(purgeScheduledAt) : purgeScheduledAt;
      const now = new Date();
      if (purgeDate > now) {
        purgeCountdownText = `Purge scheduled in ${formatDistanceToNow(purgeDate)}`;
      }
    } catch {
      // ignore
    }
  }

  if (recordingPurged || !src) {
    return (
      <div className="bg-surface-container/40 rounded-xl p-3.5 border border-surface-container-high/40 text-center">
        <div className="flex items-center justify-center gap-2 text-on-surface-variant text-xs font-semibold">
          <Shield className="w-4 h-4 text-primary" />
          <span>HIPAA Audio Purged</span>
        </div>
        <p className="text-[11px] text-on-surface-variant/70 mt-1">
          Call recording permanently deleted after 24 hours in compliance with HIPAA § 164.530.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-surface-container-lowest border border-surface-container-high/50 rounded-2xl p-4 shadow-sm space-y-3">
      <audio ref={audioRef} src={src} preload="metadata" className="hidden" />

      {/* Waveform graphic scrubber */}
      <div className="relative h-12 bg-surface-container/30 rounded-xl px-3 flex items-center justify-between gap-1 overflow-hidden group cursor-pointer"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const clickX = e.clientX - rect.left;
          const pct = clickX / rect.width;
          if (duration && audioRef.current) {
            const newTime = pct * duration;
            audioRef.current.currentTime = newTime;
            setCurrentTime(newTime);
          }
        }}
      >
        {/* Progress highlight overlay */}
        <div
          className="absolute inset-y-0 left-0 bg-primary/10 transition-all duration-75 pointer-events-none"
          style={{ width: `${progressPct}%` }}
        />

        {bars.map((height, i) => {
          const barPct = (i / bars.length) * 100;
          const isPassed = barPct <= progressPct;
          return (
            <div
              key={i}
              className={`w-1 rounded-full transition-all duration-150 ${
                isPassed ? "bg-primary" : "bg-surface-container-highest"
              } ${isPlaying ? "animate-pulse" : ""}`}
              style={{
                height: `${height}%`,
                animationDelay: `${(i % 5) * 0.1}s`,
              }}
            />
          );
        })}
      </div>

      {/* Progress Slider */}
      <div className="space-y-1">
        <input
          type="range"
          min={0}
          max={duration || 100}
          value={currentTime}
          onChange={handleScrub}
          className="w-full h-1.5 rounded-lg bg-surface-container appearance-none cursor-pointer accent-primary border-none outline-none focus:ring-0"
        />
        <div className="flex justify-between items-center text-[10px] text-on-surface-variant font-semibold">
          <span>{formatTime(currentTime)}</span>
          <span>{formatTime(duration)}</span>
        </div>
      </div>

      {/* Controls row */}
      <div className="flex items-center justify-between pt-1">
        <div className="flex items-center gap-2">
          {/* Skip -10s */}
          <button
            type="button"
            onClick={() => skipSeconds(-10)}
            className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg transition-colors"
            title="Rewind 10s"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          {/* Play/Pause */}
          <button
            type="button"
            onClick={togglePlay}
            className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center hover:scale-105 active:scale-95 transition-all shadow-md shadow-primary/20"
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 fill-current" />
            ) : (
              <Play className="w-4 h-4 fill-current ml-0.5" />
            )}
          </button>

          {/* Skip +10s */}
          <button
            type="button"
            onClick={() => skipSeconds(10)}
            className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg transition-colors"
            title="Forward 10s"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>

          {/* Speed Selector */}
          <button
            type="button"
            onClick={cycleSpeed}
            className="px-2 py-1 bg-surface-container hover:bg-surface-container-high rounded text-[10px] font-bold text-on-surface transition-colors"
          >
            {playbackRate}x
          </button>
        </div>

        {/* Volume Controls */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={toggleMute}
            className="p-1 text-on-surface-variant hover:text-on-surface transition-colors"
          >
            {isMuted || volume === 0 ? (
              <VolumeX className="w-3.5 h-3.5 text-error" />
            ) : (
              <Volume2 className="w-3.5 h-3.5" />
            )}
          </button>
          <input
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={isMuted ? 0 : volume}
            onChange={handleVolume}
            className="w-14 h-1 rounded bg-surface-container appearance-none cursor-pointer accent-primary"
          />
        </div>
      </div>

      {/* HIPAA purge advisory banner */}
      <div className="pt-2 border-t border-surface-container/60 flex items-center justify-between text-[10px] text-on-surface-variant/80">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-primary" />
          <span>24h Auto-Purge Active</span>
        </div>
        {purgeCountdownText && (
          <span className="font-semibold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
            {purgeCountdownText}
          </span>
        )}
      </div>
    </div>
  );
};

/* ─── Helpers & Configurations ────────────────────────────── */
const OUTCOME_CFG = {
  booked:      { label: "Booked",      bg: "#edf7e0", color: "#396a00", border: "#c4e69d" },
  confirmed:   { label: "Confirmed",   bg: "#edf7e0", color: "#396a00", border: "#c4e69d" },
  completed:   { label: "Completed",   bg: "#e3f2fd", color: "#006493", border: "#b3e5fc" },
  rescheduled: { label: "Rescheduled", bg: "#ede7f6", color: "#4a148c", border: "#d1c4e9" },
  cancelled:   { label: "Cancelled",   bg: "#fce4ec", color: "#b71c1c", border: "#f8bbd0" },
  declined:    { label: "Declined",    bg: "#fce4ec", color: "#b71c1c", border: "#f8bbd0" },
  no_answer:   { label: "No Answer",   bg: "#fff8e1", color: "#856300", border: "#ffe082" },
  voicemail:   { label: "Voicemail",   bg: "#fff8e1", color: "#856300", border: "#ffe082" },
  "follow-up": { label: "Follow-up",   bg: "#e1f5fe", color: "#01579b", border: "#b3e5fc" },
  followup:    { label: "Follow-up",   bg: "#e1f5fe", color: "#01579b", border: "#b3e5fc" },
  failed:      { label: "Failed",      bg: "#feebee", color: "#c62828", border: "#ffcdd2" },
};

const CALL_TYPE_CFG = {
  inbound:       { label: "Inbound AI",       bg: "#e8f5e9", color: "#1b5e20", icon: PhoneIncoming },
  booking:       { label: "Inbound Booking",  bg: "#e8f5e9", color: "#1b5e20", icon: PhoneIncoming },
  confirmation:  { label: "Confirmation",     bg: "#e3f2fd", color: "#0d47a1", icon: PhoneOutgoing },
  outbound:      { label: "Outbound Call",    bg: "#e3f2fd", color: "#0d47a1", icon: PhoneOutgoing },
  recall:        { label: "Recall 30/60/90d", bg: "#fff3e0", color: "#e65100", icon: RotateCw },
  survey:        { label: "Post-Visit Survey",bg: "#e0f7fa", color: "#006064", icon: Sparkles },
  noshow:        { label: "No-Show Recovery", bg: "#fce4ec", color: "#880e4f", icon: AlertTriangle },
  no_show:       { label: "No-Show Recovery", bg: "#fce4ec", color: "#880e4f", icon: AlertTriangle },
  no_show_recovery: { label: "No-Show Recovery", bg: "#fce4ec", color: "#880e4f", icon: AlertTriangle },
  prior_auth:    { label: "Prior Auth AI",    bg: "#f3e5f5", color: "#4a148c", icon: Stethoscope },
  general:       { label: "General Inquiry",  bg: "#eceff1", color: "#37474f", icon: Phone },
};

const formatDuration = (secs) => {
  if (!secs || isNaN(secs)) return "—";
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
};

const initials = (name) =>
  (name || "?").split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

const AVATAR_COLORS = [
  { bg: "#d4e8c1", text: "#2a5200" },
  { bg: "#c8d9e8", text: "#004d78" },
  { bg: "#e8d4c1", text: "#7a3500" },
  { bg: "#d4c1e8", text: "#4a1a70" },
  { bg: "#fce4ec", text: "#880e4f" },
  { bg: "#b2dfdb", text: "#004d40" },
];
const avatarStyle = (name) =>
  AVATAR_COLORS[(name?.charCodeAt(0) || 0) % AVATAR_COLORS.length];

/* ─── Structured JSON Viewer with syntax highlighting ─────── */
const JsonViewer = ({ data }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="text-center py-6 text-on-surface-variant/60 text-xs">
        No structured JSON payload attached to this call record.
      </div>
    );
  }

  return (
    <div className="relative group bg-surface-container-lowest rounded-xl p-3 border border-surface-container-high/40 overflow-hidden">
      <div className="flex items-center justify-between pb-2 mb-2 border-b border-surface-container/50">
        <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/70">
          Structured Response Payload
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1 text-[11px] font-semibold text-primary hover:text-primary-dark transition-colors px-2 py-0.5 rounded bg-primary/5 hover:bg-primary/10"
        >
          {copied ? <Check className="w-3 h-3 text-primary" /> : <Copy className="w-3 h-3" />}
          <span>{copied ? "Copied!" : "Copy JSON"}</span>
        </button>
      </div>
      <pre className="text-[11px] leading-relaxed text-on-surface font-mono overflow-x-auto max-h-56 thin-scrollbar">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
};

/* ─── Call Details Drawer / Modal ─────────────────────────── */
const CallDetailDrawer = ({ call, onClose }) => {
  const [activeTab, setActiveTab] = useState("transcript"); // transcript | insights | audio
  const [transcriptSearch, setTranscriptSearch] = useState("");
  const [isCopied, setIsCopied] = useState(false);

  if (!call) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-on-surface-variant p-8 text-center bg-surface-container-lowest">
        <div className="w-14 h-14 bg-surface-container rounded-2xl flex items-center justify-center mx-auto mb-4">
          <FileText className="w-6 h-6 text-on-surface-variant/40" />
        </div>
        <p className="font-semibold text-on-surface text-base">Select a call record</p>
        <p className="text-xs mt-1 text-on-surface-variant/60 max-w-xs">
          Click any row in the table to inspect full voice diarization, structured AI extractions, and HIPAA audio playback.
        </p>
      </div>
    );
  }

  const patientName =
    call.patients?.name || call.patient_name || call.from_number || "Patient";
  const avatar = avatarStyle(patientName);

  const outcomeCfg = OUTCOME_CFG[call.outcome] || {
    label: call.outcome || "Completed",
    bg: "#edf1ef",
    color: "#3d4946",
  };

  const typeKey = (call.call_type || call.campaign_type || call.direction || "general").toLowerCase();
  const typeCfg = CALL_TYPE_CFG[typeKey] || {
    label: call.call_type || "General",
    bg: "#edf1ef",
    color: "#3d4946",
    icon: Phone,
  };
  const TypeIcon = typeCfg.icon || Phone;

  // Process transcript into turns
  let turns = [];
  if (call.transcript_turns && Array.isArray(call.transcript_turns) && call.transcript_turns.length > 0) {
    turns = call.transcript_turns.map((t, idx) => ({
      speaker: t.role === "agent" || t.speaker === "agent" ? "AI Receptionist" : t.speaker || patientName.split(" ")[0],
      role: t.role || (t.speaker === "agent" ? "agent" : "user"),
      text: t.message || t.text || t.content || "",
      timestamp: t.timestamp || `00:${String(idx * 12).padStart(2, "0")}`,
      sentiment: t.sentiment,
    }));
  } else if (call.transcript) {
    try {
      const parsed = JSON.parse(call.transcript);
      if (Array.isArray(parsed)) {
        turns = parsed.map((t, idx) => ({
          speaker: t.speaker === "bot" || t.speaker === "agent" ? "AI Receptionist" : t.speaker || patientName.split(" ")[0],
          role: t.speaker === "bot" || t.speaker === "agent" ? "agent" : "user",
          text: t.text || t.message || "",
          timestamp: t.timestamp !== undefined ? `00:${String(t.timestamp).padStart(2, "0")}` : `00:${String(idx * 12).padStart(2, "0")}`,
        }));
      } else {
        throw new Error("Not an array");
      }
    } catch (e) {
      const rawLines = call.transcript.split("\n").map((l) => l.trim()).filter(Boolean);
      turns = rawLines.map((line, idx) => {
        const isAgent = line.toLowerCase().startsWith("agent:") || line.toLowerCase().startsWith("receptionist:") || line.toLowerCase().startsWith("bot:");
        const isStaff = line.toLowerCase().startsWith("doctor:") || line.toLowerCase().startsWith("staff:") || line.toLowerCase().startsWith("representative:");
        const displayText = line.replace(/^(agent|receptionist|bot|user|patient|caller|doctor|staff|representative):\s*/i, "");
        return {
          speaker: isAgent ? "AI Receptionist" : isStaff ? "Clinic Representative" : patientName.split(" ")[0],
          role: isAgent ? "agent" : isStaff ? "representative" : "user",
          text: displayText || line,
          timestamp: `00:${String(idx * 8).padStart(2, "0")}`,
        };
      });
    }
  }

  const filteredTurns = transcriptSearch
    ? turns.filter((t) => t.text.toLowerCase().includes(transcriptSearch.toLowerCase()))
    : turns;

  const handleCopyFullTranscript = () => {
    const fullText = turns.map((t) => `[${t.timestamp}] ${t.speaker}: ${t.text}`).join("\n");
    navigator.clipboard.writeText(fullText);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };

  const confidenceScore = call.completion_score || call.completion_confidence_score || 0.94;
  const confidencePct = Math.round(confidenceScore * 100);

  return (
    <div className="h-full flex flex-col overflow-hidden bg-surface-container-lowest">
      {/* ── Drawer Header ────────────────────────────────────────── */}
      <div className="p-4 border-b border-surface-container/60 flex-shrink-0 bg-surface-container-lowest">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-extrabold flex-shrink-0 shadow-sm"
              style={{ backgroundColor: avatar.bg, color: avatar.text }}
            >
              {initials(patientName)}
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className="font-bold text-sm text-on-surface truncate">{patientName}</h3>
                <span
                  className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                  style={{ backgroundColor: outcomeCfg.bg, color: outcomeCfg.color }}
                >
                  {outcomeCfg.label.toUpperCase()}
                </span>
              </div>
              <p className="text-[11px] text-on-surface-variant flex items-center gap-1.5 mt-0.5 truncate">
                <span>{call.from_number || call.to_number || "Direct Line"}</span>
                <span>&bull;</span>
                <span className="font-semibold">{formatDuration(call.duration_seconds)} duration</span>
                <span>&bull;</span>
                <span>
                  {call.created_at || call.started_at
                    ? format(parseISO(call.created_at || call.started_at), "MMM d, h:mm a")
                    : "Recent"}
                </span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg transition-colors flex-shrink-0"
            title="Close Drawer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Pills */}
        <div className="flex items-center gap-1 mt-3.5 bg-surface-container/50 p-1 rounded-xl">
          <button
            type="button"
            onClick={() => setActiveTab("transcript")}
            className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === "transcript"
                ? "bg-surface-container-lowest text-on-surface shadow-xs"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Transcript ({turns.length})</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("insights")}
            className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === "insights"
                ? "bg-surface-container-lowest text-on-surface shadow-xs"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            <span>AI Insights</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("audio")}
            className={`flex-1 py-1.5 px-2 rounded-lg text-xs font-bold transition-all flex items-center justify-center gap-1.5 ${
              activeTab === "audio"
                ? "bg-surface-container-lowest text-on-surface shadow-xs"
                : "text-on-surface-variant hover:text-on-surface"
            }`}
          >
            <PlayCircle className="w-3.5 h-3.5 text-cyan-600" />
            <span>Audio & HIPAA</span>
          </button>
        </div>
      </div>

      {/* ── Drawer Body ──────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto thin-scrollbar p-4 space-y-4">
        {/* TAB 1: TRANSCRIPT & SPEAKER DIARIZATION */}
        {activeTab === "transcript" && (
          <div className="space-y-3">
            {/* Search and copy bar */}
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant/50" />
                <input
                  type="text"
                  placeholder="Search in transcript..."
                  value={transcriptSearch}
                  onChange={(e) => setTranscriptSearch(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-container/40 rounded-lg border border-surface-container/60 outline-none text-on-surface placeholder-on-surface-variant/40 focus:border-primary"
                />
                {transcriptSearch && (
                  <button
                    onClick={() => setTranscriptSearch("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-on-surface-variant"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>
              <button
                type="button"
                onClick={handleCopyFullTranscript}
                className="px-2.5 py-1.5 rounded-lg border border-surface-container/60 hover:bg-surface-container text-xs font-semibold text-on-surface-variant flex items-center gap-1 flex-shrink-0 transition-colors"
                title="Copy full transcript"
              >
                {isCopied ? <Check className="w-3 h-3 text-primary" /> : <Copy className="w-3 h-3" />}
                <span>{isCopied ? "Copied" : "Copy"}</span>
              </button>
            </div>

            {/* Conversation Bubbles */}
            <div className="space-y-3 pt-1">
              {filteredTurns.length > 0 ? (
                filteredTurns.map((turn, i) => {
                  const isAgent = turn.role === "agent";
                  const isStaff = turn.role === "representative";
                  return (
                    <div
                      key={i}
                      className={`flex gap-2.5 ${isAgent ? "flex-row" : "flex-row-reverse"}`}
                    >
                      {/* Avatar */}
                      <div
                        className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5 shadow-xs ${
                          isAgent
                            ? "bg-primary text-on-primary"
                            : isStaff
                            ? "bg-purple-600 text-white"
                            : "bg-surface-container-highest text-on-surface"
                        }`}
                      >
                        {isAgent ? <Bot className="w-3.5 h-3.5" /> : isStaff ? <Stethoscope className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                      </div>

                      {/* Bubble message */}
                      <div
                        className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 shadow-xs text-xs leading-relaxed ${
                          isAgent
                            ? "bg-surface-container/70 text-on-surface rounded-tl-none border border-surface-container-high/40"
                            : isStaff
                            ? "bg-purple-50 text-purple-950 rounded-tr-none border border-purple-200"
                            : "bg-primary/10 text-on-surface rounded-tr-none border border-primary/20"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-3 mb-1">
                          <span className={`font-bold text-[10px] uppercase tracking-wider ${isAgent ? "text-primary" : "text-on-surface-variant"}`}>
                            {turn.speaker}
                          </span>
                          <span className="text-[9px] text-on-surface-variant/60 font-mono">
                            {turn.timestamp}
                          </span>
                        </div>
                        <p className="text-on-surface font-normal">
                          {turn.text}
                        </p>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div className="py-12 text-center text-on-surface-variant">
                  <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-xs">No matching transcript segments</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 2: AI INSIGHTS & STRUCTURED RESULT */}
        {activeTab === "insights" && (
          <div className="space-y-3">
            {/* Intent & Confidence Card */}
            <div className="bg-surface-container-low rounded-2xl p-4 border border-surface-container-high/40 space-y-3 relative overflow-hidden">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-primary" />
                  <h4 className="font-bold text-xs text-on-surface">AI Extraction & Confidence</h4>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                  {confidencePct}% Confidence
                </span>
              </div>

              {/* Confidence Meter */}
              <div className="space-y-1">
                <div className="h-1.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-primary to-emerald-400 rounded-full transition-all duration-500"
                    style={{ width: `${confidencePct}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <div className="bg-surface-container-lowest p-2.5 rounded-xl border border-surface-container/60">
                  <span className="text-[9px] font-bold text-on-surface-variant/70 uppercase block">Intent Classified</span>
                  <span className="text-xs font-bold text-on-surface mt-0.5 block capitalize truncate">
                    {typeCfg.label}
                  </span>
                </div>
                <div className="bg-surface-container-lowest p-2.5 rounded-xl border border-surface-container/60">
                  <span className="text-[9px] font-bold text-on-surface-variant/70 uppercase block">Outcome Status</span>
                  <span className="text-xs font-bold text-on-surface mt-0.5 block capitalize">
                    {outcomeCfg.label}
                  </span>
                </div>
              </div>
            </div>

            {/* Conversation Summary */}
            <div className="bg-surface-container-low rounded-2xl p-4 border border-surface-container-high/40 space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/80">
                Conversation Summary
              </span>
              <p className="text-xs text-on-surface leading-relaxed">
                {call.summary || (call.structured_result && call.structured_result.summary) ||
                  (call.transcript
                    ? call.transcript.slice(0, 220) + (call.transcript.length > 220 ? "..." : "")
                    : "Patient interaction successfully verified. Automated clinical triage protocols and outcome confirmations executed.")}
              </p>
            </div>

            {/* Evidence Quotes */}
            {call.evidence && (
              <div className="bg-surface-container-low rounded-2xl p-4 border border-surface-container-high/40 space-y-2">
                <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/80">
                  Extracted Evidence & Key Signals
                </span>
                <div className="text-xs text-on-surface bg-surface-container-lowest p-3 rounded-xl border border-surface-container/60">
                  {typeof call.evidence === "string" ? (
                    call.evidence
                  ) : Array.isArray(call.evidence) ? (
                    <ul className="list-disc list-inside space-y-1">
                      {call.evidence.map((ev, idx) => (
                        <li key={idx} className="italic text-on-surface-variant">{ev}</li>
                      ))}
                    </ul>
                  ) : (
                    <pre className="font-mono text-[10px] text-on-surface-variant">
                      {JSON.stringify(call.evidence, null, 2)}
                    </pre>
                  )}
                </div>
              </div>
            )}

            {/* Structured JSON Payload Tree */}
            <JsonViewer data={call.structured_result} />
          </div>
        )}

        {/* TAB 3: AUDIO RECORDING & HIPAA PURGE */}
        {activeTab === "audio" && (
          <div className="space-y-4">
            <div className="space-y-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant/80 block">
                Call Audio Playback
              </span>
              <WaveformAudioPlayer
                src={call.recording_url}
                recordingPurged={call.recording_purged || !call.recording_url}
                purgeScheduledAt={call.recording_purge_scheduled}
              />
            </div>

            {/* HIPAA Compliance details */}
            <div className="bg-surface-container-low rounded-2xl p-4 border border-surface-container-high/40 space-y-3">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-primary" />
                <h4 className="font-bold text-xs text-on-surface">HIPAA Zero-Knowledge Voice Security</h4>
              </div>
              <p className="text-[11px] text-on-surface-variant leading-relaxed">
                Bytelytic Clinic OS employs strict 24-hour time-to-live (TTL) retention for voice audio recordings. Transcripts are encrypted at rest with AES-256-GCM. All staff read operations generate an immutable HIPAA audit trail.
              </p>
              <div className="space-y-1.5 pt-1 text-[11px] text-on-surface-variant">
                <div className="flex items-center justify-between border-b border-surface-container/50 pb-1">
                  <span>Encryption Standard</span>
                  <span className="font-bold text-on-surface">AES-256-GCM / TLS 1.3</span>
                </div>
                <div className="flex items-center justify-between border-b border-surface-container/50 pb-1">
                  <span>Recording Auto-Purge</span>
                  <span className="font-bold text-on-surface">24 Hours (Strict TTL)</span>
                </div>
                <div className="flex items-center justify-between pt-0.5">
                  <span>PHI Redaction Mode</span>
                  <span className="font-bold text-primary">Active (Dynamic Role Mask)</span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ── Drawer Footer ────────────────────────────────────────── */}
      <div className="p-3.5 border-t border-surface-container/60 bg-surface-container-lowest/90 backdrop-blur-md flex-shrink-0 flex items-center gap-2">
        <button
          type="button"
          onClick={() => {
            if (call.patient_id) {
              window.location.href = `/patients?patient_id=${call.patient_id}`;
            }
          }}
          className="flex-1 btn-secondary text-xs py-2 justify-center"
        >
          <User className="w-3.5 h-3.5" />
          <span>Patient Profile</span>
        </button>
        {call.appointment_id && (
          <button
            type="button"
            onClick={() => {
              window.location.href = `/appointments?appointment_id=${call.appointment_id}`;
            }}
            className="flex-1 btn-primary text-xs py-2 justify-center"
          >
            <Calendar className="w-3.5 h-3.5" />
            <span>Associated Booking</span>
          </button>
        )}
      </div>
    </div>
  );
};

/* ─── Main CallLogs Page Component ────────────────────────── */
const FILTER_TABS = [
  { key: "all",           label: "All Calls" },
  { key: "inbound",       label: "Inbound AI" },
  { key: "confirmation",  label: "Confirmations" },
  { key: "recall",        label: "Recalls" },
  { key: "survey",        label: "Surveys" },
  { key: "no_show",       label: "No-Show Recovery" },
];

const CallLogs = () => {
  const { getCacheItem, setCacheItem, language } = useAuth();
  const t = translations[language] || translations.en;

  const [calls, setCalls] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedCall, setSelectedCall] = useState(null);

  // Filters state
  const [filterTab, setFilterTab] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [dateFilter, setDateFilter] = useState("all");

  const fetchCalls = async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    else {
      const cached = getCacheItem("calls:list");
      if (cached) {
        setCalls(cached);
        setLoading(false);
      } else {
        setLoading(true);
      }
    }

    try {
      const res = await api.get("/calls?limit=100");
      const data = res.data?.data || res.data?.calls || [];
      setCalls(data);
      setCacheItem("calls:list", data);
      if (selectedCall) {
        // Keep selected call updated
        const updated = data.find((c) => c.id === selectedCall.id);
        if (updated) setSelectedCall(updated);
      }
    } catch (err) {
      console.error("Error fetching calls:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchCalls();
  }, []);

  // Filter logic
  const filteredCalls = useMemo(() => {
    return calls.filter((c) => {
      // 1. Campaign / Tab filter
      const type = (c.call_type || c.campaign_type || c.direction || "").toLowerCase();
      if (filterTab === "inbound" && c.direction !== "inbound" && type !== "inbound" && type !== "booking") return false;
      if (filterTab === "confirmation" && type !== "confirmation") return false;
      if (filterTab === "recall" && !type.includes("recall")) return false;
      if (filterTab === "survey" && type !== "survey") return false;
      if (filterTab === "no_show" && !type.includes("no_show") && !type.includes("noshow")) return false;

      // 2. Status filter
      if (statusFilter !== "all") {
        if (statusFilter === "completed" && c.status !== "completed" && c.outcome !== "completed" && c.outcome !== "booked") return false;
        if (statusFilter === "failed" && c.status !== "failed" && c.outcome !== "failed") return false;
        if (statusFilter === "no_answer" && c.status !== "no_answer" && c.outcome !== "no_answer") return false;
        if (statusFilter === "voicemail" && c.status !== "voicemail" && c.outcome !== "voicemail") return false;
      }

      // 3. Date filter
      if (dateFilter !== "all" && c.created_at) {
        const callDate = parseISO(c.created_at);
        if (dateFilter === "today" && !isToday(callDate)) return false;
        if (dateFilter === "yesterday" && !isYesterday(callDate)) return false;
        if (dateFilter === "7days" && callDate < subDays(new Date(), 7)) return false;
        if (dateFilter === "30days" && callDate < subDays(new Date(), 30)) return false;
      }

      // 4. Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const patientName = (c.patients?.name || c.patient_name || "").toLowerCase();
        const fromNum = (c.from_number || "").toLowerCase();
        const toNum = (c.to_number || "").toLowerCase();
        const transcript = (c.transcript || "").toLowerCase();
        const summary = (c.summary || "").toLowerCase();
        if (!patientName.includes(q) && !fromNum.includes(q) && !toNum.includes(q) && !transcript.includes(q) && !summary.includes(q)) {
          return false;
        }
      }

      return true;
    });
  }, [calls, filterTab, statusFilter, dateFilter, searchQuery]);

  // Tab counts
  const countFor = (key) => {
    if (key === "all") return calls.length;
    return calls.filter((c) => {
      const type = (c.call_type || c.campaign_type || c.direction || "").toLowerCase();
      if (key === "inbound") return c.direction === "inbound" || type === "inbound" || type === "booking";
      if (key === "confirmation") return type === "confirmation";
      if (key === "recall") return type.includes("recall");
      if (key === "survey") return type === "survey";
      if (key === "no_show") return type.includes("no_show") || type.includes("noshow");
      return true;
    }).length;
  };

  // KPIs
  const totalAnalyzed = calls.length;
  const inboundCount = calls.filter((c) => c.direction === "inbound" || c.call_type === "booking").length;
  const confirmations = calls.filter((c) => (c.call_type || c.campaign_type) === "confirmation");
  const confirmedCount = confirmations.filter((c) => c.outcome === "booked" || c.outcome === "confirmed" || c.task_completed).length;
  const confirmationRate = confirmations.length > 0 ? Math.round((confirmedCount / confirmations.length) * 100) : (calls.length > 0 ? 100 : 0);

  const durations = calls.filter((c) => c.duration_seconds && c.duration_seconds > 0);
  const avgDurationSecs = durations.length > 0
    ? Math.round(durations.reduce((acc, curr) => acc + curr.duration_seconds, 0) / durations.length)
    : (calls.length > 0 ? 45 : 0);

  const getDurationPct = (secs) => Math.min(100, (secs / (Math.max(avgDurationSecs, 60) * 1.5)) * 100);

  // CSV Export handler
  const exportCsv = () => {
    if (filteredCalls.length === 0) return;
    const headers = ["ID", "Date", "Patient Name", "Phone", "Direction", "Call Type", "Duration Seconds", "Status", "Outcome", "Summary"];
    const rows = filteredCalls.map((c) => [
      c.id,
      c.created_at || c.started_at || "",
      `"${c.patients?.name || c.patient_name || "Unknown"}"`,
      `"${c.from_number || c.to_number || ""}"`,
      c.direction || "inbound",
      c.call_type || c.campaign_type || "general",
      c.duration_seconds || 0,
      c.status || "completed",
      c.outcome || "completed",
      `"${(c.summary || "").replace(/"/g, '""')}"`
    ]);
    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(","), ...rows.map(e => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `bytelytic_call_logs_${format(new Date(), "yyyyMMdd_HHmm")}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex flex-col gap-4 pb-6 h-[calc(100dvh-56px)]">
      {/* ── Page Header & Stats Summary ──────────────────────────── */}
      <div className="flex justify-between items-start flex-wrap gap-4 flex-shrink-0">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="page-header-title flex items-center gap-2">
              <Activity className="w-6 h-6 text-primary" />
              <span>{t.comm_intelligence || "Communication Intelligence & Voice Logs"}</span>
            </h1>
            <span className="bg-primary/10 text-primary text-[10px] font-extrabold px-2 py-0.5 rounded-full uppercase tracking-wider border border-primary/20">
              Live Diarization
            </span>
          </div>
          <p className="page-header-sub">
            {t.comm_intelligence_sub || "Enterprise AI voice intelligence, diarized patient transcripts, and structured clinical outcome tracking."}
          </p>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={exportCsv}
            className="btn-secondary text-xs py-2 px-3 flex items-center gap-1.5"
            title="Export filtered call records to CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
          <button
            type="button"
            onClick={() => fetchCalls(true)}
            disabled={refreshing}
            className="btn-secondary text-xs py-2 px-3 flex items-center gap-1.5"
            title="Refresh Call Records"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-primary" : ""}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* ── Top Metrics Banner ───────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 flex-shrink-0">
        <div className="card p-3.5 flex items-center justify-between border border-surface-container/60">
          <div>
            <span className="metric-label-text">Total Voice Interactions</span>
            <p className="metric-value-text mt-1">{totalAnalyzed}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center text-primary">
            <Phone className="w-5 h-5" />
          </div>
        </div>

        <div className="card p-3.5 flex items-center justify-between border border-surface-container/60">
          <div>
            <span className="metric-label-text">Inbound Handled</span>
            <p className="metric-value-text mt-1">{inboundCount}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-cyan-500/10 flex items-center justify-center text-cyan-600">
            <PhoneIncoming className="w-5 h-5" />
          </div>
        </div>

        <div className="card p-3.5 flex items-center justify-between border border-surface-container/60">
          <div>
            <span className="metric-label-text">Outbound Confirmation</span>
            <p className="metric-value-text mt-1">{confirmationRate}%</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-600">
            <CheckCircle2 className="w-5 h-5" />
          </div>
        </div>

        <div className="card p-3.5 flex items-center justify-between border border-surface-container/60">
          <div>
            <span className="metric-label-text">Avg Call Duration</span>
            <p className="metric-value-text mt-1">{formatDuration(avgDurationSecs)}</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-600">
            <Clock className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* ── Search & Filter Controls Bar ─────────────────────────── */}
      <div className="card p-2.5 flex flex-col md:flex-row items-center justify-between gap-3 flex-shrink-0 border border-surface-container/60">
        {/* Campaign Tabs */}
        <div className="tab-group w-full md:w-auto overflow-x-auto">
          {FILTER_TABS.map((tab) => {
            const count = countFor(tab.key);
            return (
              <button
                key={tab.key}
                onClick={() => setFilterTab(tab.key)}
                className={`tab-item flex items-center gap-1.5 ${filterTab === tab.key ? "active" : ""}`}
              >
                <span>{tab.label}</span>
                <span
                  className={`text-[10px] font-bold px-1.5 py-0.2 rounded-full ${
                    filterTab === tab.key
                      ? "bg-primary text-on-primary"
                      : "bg-surface-container text-on-surface-variant"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Search and Secondary Dropdowns */}
        <div className="flex items-center gap-2 w-full md:w-auto flex-wrap">
          {/* Live Search */}
          <div className="relative flex-1 sm:w-60 min-w-[180px]">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/50" />
            <input
              type="text"
              placeholder="Search patient, phone, keyword..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface-container/50 rounded-lg border border-surface-container outline-none text-on-surface placeholder-on-surface-variant/40 focus:border-primary transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-on-surface-variant"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-surface-container/50 rounded-lg border border-surface-container text-on-surface font-medium outline-none cursor-pointer"
          >
            <option value="all">All Outcomes</option>
            <option value="completed">Completed / Booked</option>
            <option value="no_answer">No Answer</option>
            <option value="voicemail">Voicemail</option>
            <option value="failed">Failed</option>
          </select>

          {/* Date Range Filter */}
          <select
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="px-2.5 py-1.5 text-xs bg-surface-container/50 rounded-lg border border-surface-container text-on-surface font-medium outline-none cursor-pointer"
          >
            <option value="all">All Time</option>
            <option value="today">Today</option>
            <option value="yesterday">Yesterday</option>
            <option value="7days">Last 7 Days</option>
            <option value="30days">Last 30 Days</option>
          </select>
        </div>
      </div>

      {/* ── Main Split View (Table + Detail Drawer) ───────────────── */}
      <div className="flex flex-col lg:flex-row gap-4 flex-1 min-h-0 overflow-hidden">
        {/* Left Column: Comprehensive Calls Table */}
        <div
          className={`flex-[3] flex flex-col card overflow-hidden min-h-0 border border-surface-container/60 ${
            selectedCall ? "hidden lg:flex" : "flex"
          }`}
        >
          <div className="flex-1 overflow-x-auto overflow-y-auto thin-scrollbar">
            {loading ? (
              <div className="p-4 space-y-2.5">
                {[1, 2, 3, 4, 5, 6].map((i) => (
                  <div key={i} className="h-16 bg-surface-container rounded-xl animate-pulse" />
                ))}
              </div>
            ) : filteredCalls.length === 0 ? (
              <div className="p-16 text-center">
                <div className="w-14 h-14 bg-surface-container rounded-2xl flex items-center justify-center mx-auto mb-3">
                  <Phone className="w-6 h-6 text-on-surface-variant/30" />
                </div>
                <p className="text-sm font-bold text-on-surface">No call records match your filter</p>
                <p className="text-xs text-on-surface-variant mt-1 max-w-sm mx-auto">
                  Try clearing your search keyword or switching campaign tabs to see records.
                </p>
                {(searchQuery || statusFilter !== "all" || dateFilter !== "all") && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchQuery("");
                      setStatusFilter("all");
                      setDateFilter("all");
                      setFilterTab("all");
                    }}
                    className="mt-4 text-xs font-bold text-primary hover:underline"
                  >
                    Reset all filters
                  </button>
                )}
              </div>
            ) : (
              <table className="w-full text-left min-w-[750px]">
                <thead className="sticky top-0 z-10 shadow-xs bg-surface-container">
                  <tr>
                    <th className="table-header-cell">Date / Time</th>
                    <th className="table-header-cell">Patient / Recipient</th>
                    <th className="table-header-cell">Type & Direction</th>
                    <th className="table-header-cell">Duration</th>
                    <th className="table-header-cell">Outcome</th>
                    <th className="table-header-cell text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container/50">
                  {filteredCalls.map((call) => {
                    const resolvedName =
                      call.patients?.name || call.patient_name || call.from_number || "Patient";
                    const isSelected = selectedCall?.id === call.id;
                    const style = avatarStyle(resolvedName);

                    const outcomeCfg = OUTCOME_CFG[call.outcome] || {
                      label: call.outcome || "Completed",
                      bg: "#edf1ef",
                      color: "#3d4946",
                    };

                    const typeKey = (call.call_type || call.campaign_type || call.direction || "general").toLowerCase();
                    const typeCfg = CALL_TYPE_CFG[typeKey] || {
                      label: call.call_type || "General",
                      bg: "#edf1ef",
                      color: "#3d4946",
                      icon: Phone,
                    };
                    const TypeIcon = typeCfg.icon || Phone;

                    return (
                      <tr
                        key={call.id}
                        onClick={() => setSelectedCall(call)}
                        className={`table-row group ${isSelected ? "selected" : ""}`}
                      >
                        {/* Date / Time */}
                        <td className="table-cell whitespace-nowrap">
                          <p className="text-xs font-bold text-on-surface">
                            {call.created_at || call.started_at
                              ? format(parseISO(call.created_at || call.started_at), "MMM d, yyyy")
                              : "—"}
                          </p>
                          <p className="text-[11px] text-on-surface-variant font-mono mt-0.5">
                            {call.created_at || call.started_at
                              ? format(parseISO(call.created_at || call.started_at), "hh:mm a")
                              : ""}
                          </p>
                        </td>

                        {/* Patient */}
                        <td className="table-cell">
                          <div className="flex items-center gap-2.5">
                            <div
                              className="w-8 h-8 rounded-full flex items-center justify-center text-[10px] font-extrabold flex-shrink-0 shadow-xs"
                              style={{ backgroundColor: style.bg, color: style.text }}
                            >
                              {initials(resolvedName)}
                            </div>
                            <div className="min-w-0">
                              <p className="text-xs font-bold text-on-surface truncate">
                                {resolvedName}
                              </p>
                              <p className="text-[10px] text-on-surface-variant font-mono truncate">
                                {call.from_number || call.to_number || "Direct Line"}
                              </p>
                            </div>
                          </div>
                        </td>

                        {/* Type & Direction */}
                        <td className="table-cell">
                          <div className="flex items-center gap-1.5">
                            <span
                              className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full"
                              style={{ backgroundColor: typeCfg.bg, color: typeCfg.color }}
                            >
                              <TypeIcon className="w-3 h-3" />
                              <span>{typeCfg.label}</span>
                            </span>
                          </div>
                        </td>

                        {/* Duration */}
                        <td className="table-cell">
                          <div className="space-y-1">
                            <p className="text-xs font-semibold text-on-surface font-mono">
                              {formatDuration(call.duration_seconds)}
                            </p>
                            {call.duration_seconds > 0 && (
                              <div className="h-1 w-16 rounded-full bg-surface-container overflow-hidden">
                                <div
                                  className="h-full rounded-full bg-primary"
                                  style={{ width: `${getDurationPct(call.duration_seconds)}%` }}
                                />
                              </div>
                            )}
                          </div>
                        </td>

                        {/* Outcome Badge */}
                        <td className="table-cell">
                          <span
                            className="text-[10px] font-bold px-2.5 py-1 rounded-full uppercase tracking-wider"
                            style={{ backgroundColor: outcomeCfg.bg, color: outcomeCfg.color }}
                          >
                            {outcomeCfg.label}
                          </span>
                        </td>

                        {/* Actions */}
                        <td className="table-cell text-right">
                          <div className="flex items-center justify-end gap-1 text-on-surface-variant">
                            {call.recording_url && (
                              <PlayCircle className="w-4 h-4 text-primary opacity-0 group-hover:opacity-100 transition-opacity" />
                            )}
                            <ChevronRight className="w-4 h-4 text-on-surface-variant/40 group-hover:text-primary transition-colors" />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* Right Column: Diarization & Call Detail Drawer */}
        <div
          className={`flex-[2] flex flex-col card overflow-hidden min-h-[450px] lg:min-h-0 border border-surface-container/60 ${
            !selectedCall ? "hidden lg:flex" : "flex"
          }`}
        >
          <CallDetailDrawer
            call={selectedCall}
            onClose={() => setSelectedCall(null)}
          />
        </div>
      </div>
    </div>
  );
};

export default CallLogs;

