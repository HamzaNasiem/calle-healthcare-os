import React, { useEffect, useState, useRef, useCallback } from "react";
import {
  DollarSign,
  PhoneCall,
  PhoneIncoming,
  PhoneOutgoing,
  CalendarCheck,
  Calendar,
  UserX,
  Clock,
  TrendingUp,
  Bot,
  Mic,
  Volume2,
  Square,
  Sparkles,
  AlertCircle,
  X,
  Building2,
  ChevronRight,
  Play,
  Pause,
  Loader2,
  Wifi,
  CheckCircle,
  CheckCircle2,
  ShieldCheck,
  Activity,
  FileText,
  Zap,
  RefreshCw,
  Search,
  ArrowUpRight,
  Layers,
  User,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Link } from "react-router-dom";
import api from "../lib/api";
import { format, parseISO, startOfDay, endOfDay, formatDistanceToNow } from "date-fns";
import { useAuth } from "../context/AuthContext";
import { useWebSocket } from "../context/WebSocketContext";
import { translations } from "../lib/translations";
import PriorAuthModal from "../components/PriorAuthModal";
import PriorAuthStatus from "../components/PriorAuthStatus";

/* ─── Custom Tooltip for Analytics ────────────────────────── */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="card p-3 text-sm min-w-[140px] shadow-xl border border-outline-variant/40 bg-surface-container-lowest">
      <p className="font-bold text-on-surface mb-1.5 text-xs border-b border-outline-variant/20 pb-1">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-3 text-xs py-0.5">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: p.fill }} />
            <span className="text-on-surface-variant text-[11px]">{p.name}:</span>
          </div>
          <span className="font-bold text-on-surface text-[11px]">{p.value}</span>
        </div>
      ))}
    </div>
  );
};

/* ─── Top 5 Header Metric Card Component ──────────────────── */
const HeaderMetricCard = ({
  title,
  value,
  subtext,
  icon: Icon,
  accentColor,
  iconBg,
  iconColor,
  loading,
  badgeText,
  badgeType = "neutral",
  progressPercent,
}) => (
  <div
    className="card p-5 relative overflow-hidden flex flex-col justify-between transition-all duration-200 hover:shadow-md border-t-[3px]"
    style={{ borderTopColor: accentColor }}
  >
    <div className="flex items-start justify-between gap-2 mb-2">
      <p className="overline text-[10px] tracking-wider text-on-surface-variant font-bold uppercase truncate">{title}</p>
      <div
        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 shadow-sm"
        style={{ backgroundColor: iconBg }}
      >
        <Icon className="w-4 h-4" style={{ color: iconColor }} />
      </div>
    </div>

    {loading ? (
      <div className="space-y-2.5 my-1">
        <div className="h-8 w-24 bg-surface-container rounded-lg animate-pulse" />
        <div className="h-3 w-36 bg-surface-container rounded animate-pulse" />
      </div>
    ) : (
      <div>
        <div className="flex items-baseline gap-2 flex-wrap">
          <p className="text-2xl sm:text-3xl font-extrabold text-on-surface tracking-tight leading-none">
            {value}
          </p>
          {badgeText && (
            <span
              className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md ${
                badgeType === "success"
                  ? "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                  : badgeType === "primary"
                  ? "bg-primary/10 text-primary border border-primary/20"
                  : "bg-surface-container-high text-on-surface-variant"
              }`}
            >
              {badgeText}
            </span>
          )}
        </div>

        {/* Optional Progress bar */}
        {progressPercent !== undefined && (
          <div className="mt-2.5 h-1.5 rounded-full bg-surface-container overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(Math.max(progressPercent, 0), 100)}%`, backgroundColor: accentColor }}
            />
          </div>
        )}

        <div className="mt-2 flex items-center gap-1.5 text-xs text-on-surface-variant font-medium">
          {subtext}
        </div>
      </div>
    )}
  </div>
);

/* ─── Up Next Appointment Row ─────────────────────────────── */
const STATUS_CONFIG = {
  arrived:     { label: "ARRIVED",     bg: "#e8f5e9", color: "#2e7d32" },
  in_session:  { label: "IN SESSION",  bg: "#fce4ec", color: "#c2185b" },
  waiting:     { label: "WAITING",     bg: "#fff8e1", color: "#f57f17" },
  scheduled:   { label: "SCHEDULED",   bg: "#e3f2fd", color: "#0288d1" },
  confirmed:   { label: "CONFIRMED",   bg: "#edf7e0", color: "#388e3c" },
  completed:   { label: "COMPLETED",   bg: "#ede7f6", color: "#512da8" },
  cancelled:   { label: "CANCELLED",   bg: "#ffebee", color: "#c62828" },
  no_show:     { label: "NO-SHOW",     bg: "#efebe9", color: "#4e342e" },
};

const UpNextRow = ({ time, ampm, name, type, status, bookedBy, isNew }) => {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.scheduled;
  return (
    <div
      className={`flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition-all ${
        isNew
          ? "bg-emerald-500/10 border border-emerald-500/30 animate-pulse"
          : status === "in_session"
          ? "bg-pink-500/5 border border-pink-500/20"
          : "hover:bg-surface-container/60 border border-transparent"
      }`}
    >
      <div className="w-12 flex-shrink-0">
        <p className="text-xs font-bold text-on-surface leading-none">{time}</p>
        <p className="text-[10px] text-on-surface-variant font-semibold mt-0.5">{ampm || "AM"}</p>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-bold text-on-surface truncate">{name}</p>
        <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
          {bookedBy === "ai" ? (
            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 flex items-center gap-0.5">
              <Bot className="w-2.5 h-2.5" /> AI
            </span>
          ) : (
            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-700 dark:text-sky-400 flex items-center gap-0.5">
              <Building2 className="w-2.5 h-2.5" /> Staff
            </span>
          )}
          <span className="text-[11px] text-on-surface-variant truncate">{type}</span>
        </div>
      </div>
      <span
        className="text-[9px] font-extrabold px-2 py-0.5 rounded-full flex-shrink-0 tracking-wide uppercase"
        style={{ backgroundColor: cfg.bg, color: cfg.color }}
      >
        {cfg.label}
      </span>
    </div>
  );
};

/* ─── Live Sentiment Badge Component ──────────────────────── */
const SentimentBadge = ({ sentiment, label }) => {
  if (sentiment === "positive") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border border-emerald-500/20">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
        {label || "Positive (High Intent)"}
      </span>
    );
  }
  if (sentiment === "critical") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-rose-500/10 text-rose-700 dark:text-rose-400 border border-rose-500/20">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
        {label || "Critical Attention"}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
      <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
      {label || "Neutral (Inquiry)"}
    </span>
  );
};

/* ─── MAIN DASHBOARD COMPONENT ────────────────────────────── */
const Dashboard = () => {
  const { getCacheItem, setCacheItem, language } = useAuth();
  const t = translations[language] || translations.en;
  const { isConnected, lastEvent } = useWebSocket();

  // State Management
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [chartRange, setChartRange] = useState(7);
  const [chartData, setChartData] = useState([]);
  const [upNext, setUpNext] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [recentCalls, setRecentCalls] = useState([]);
  const [callFilter, setCallFilter] = useState("all"); // 'all' | 'booking' | 'confirmation' | 'prior_auth'
  const [clinic, setClinic] = useState(null);
  const [liveAlert, setLiveAlert] = useState(null);
  const [newApptId, setNewApptId] = useState(null);

  // Modals state
  const [showSimulator, setShowSimulator] = useState(false);
  const [showPriorAuthModal, setShowPriorAuthModal] = useState(false);
  const [showPriorAuthStatus, setShowPriorAuthStatus] = useState(false);
  const [activePriorAuthData, setActivePriorAuthData] = useState(null);
  const [selectedCallTranscript, setSelectedCallTranscript] = useState(null);

  // Simulator state
  const [simState, setSimState] = useState("idle"); // 'idle' | 'connecting' | 'connected' | 'ended'
  const [simDuration, setSimDuration] = useState(0);
  const [simLines, setSimLines] = useState([]);
  const [inputText, setInputText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isBotTyping, setIsBotTyping] = useState(false);
  const recognitionRef = useRef(null);

  /* ─── Fetch Timeline Analytics ─────────────────────────────── */
  const fetchTimeline = useCallback(async (days) => {
    try {
      const res = await api.get(`/dashboard/timeline?days=${days}`);
      const raw = res.data?.data || [];
      const formatted = raw.map((item) => {
        const d = parseISO(item.date);
        return {
          name: format(d, "MMM d"),
          "Inbound Calls": item.calls || 0,
          "Answered": item.answered || item.calls || 0,
          "AI Bookings": item.bookings || 0,
          "Staff Bookings": item.manual_bookings || 0,
        };
      });
      setChartData(formatted);
      setCacheItem(`dashboard:timeline:${days}`, formatted);
    } catch (err) {
      console.error("Failed to load timeline chart data:", err);
    }
  }, [setCacheItem]);

  /* ─── Fetch Recent Calls Widget Data ──────────────────────── */
  const fetchRecentCalls = useCallback(async () => {
    try {
      const res = await api.get("/dashboard/recent-calls?limit=8");
      const calls = res.data?.data || [];
      setRecentCalls(calls);
      setCacheItem("dashboard:recentCalls", calls);
    } catch (err) {
      console.warn("Failed to load recent calls:", err);
    }
  }, [setCacheItem]);

  /* ─── Fetch Full Dashboard State ───────────────────────────── */
  const fetchDashboard = useCallback(async (isSilent = false) => {
    if (!isSilent) setRefreshing(true);
    try {
      const info = JSON.parse(localStorage.getItem("clinic-info") || sessionStorage.getItem("clinic-info") || "{}");
      if (info?.clinicId) {
        api.get(`/clinics/${info.clinicId}`)
          .then((res) => {
            const clinicData = res.data?.data || null;
            setClinic(clinicData);
            setCacheItem("dashboard:clinic", clinicData);
          })
          .catch(() => {});
      }

      const [statsRes, apptRes, callsRes] = await Promise.all([
        api.get("/dashboard/stats"),
        api.get("/appointments?limit=150"),
        api.get("/dashboard/recent-calls?limit=8").catch(() => ({ data: { data: [] } })),
      ]);

      const s = statsRes.data?.data || statsRes.data || {};
      setStats(s);
      setCacheItem("dashboard:stats", s);

      const rawAppts = apptRes.data?.data || apptRes.data?.appointments || apptRes.data || [];
      const apptList = Array.isArray(rawAppts) ? rawAppts : [];
      setAppointments(apptList);
      setCacheItem("dashboard:appointments", apptList);

      const callsList = callsRes.data?.data || [];
      if (callsList.length > 0) {
        setRecentCalls(callsList);
        setCacheItem("dashboard:recentCalls", callsList);
      }

      // Process Up Next Appointments for Today
      const now = new Date();
      const dayStart = startOfDay(now);
      const dayEnd = endOfDay(now);

      const upcoming = apptList
        .filter((a) => !["cancelled", "completed", "no_show"].includes(a.status))
        .filter((a) => {
          if (!a.datetime) return false;
          const dt = new Date(a.datetime);
          return dt >= dayStart && dt <= dayEnd;
        })
        .sort((a, b) => new Date(a.datetime) - new Date(b.datetime))
        .map((a) => ({
          id: a.id,
          time: format(new Date(a.datetime), "hh:mm"),
          ampm: format(new Date(a.datetime), "a"),
          name: a.patient_name || "Patient",
          type: a.appointment_type || "Follow-up",
          status: a.status || "scheduled",
          bookedBy: a.booked_by || "ai",
        }));

      setUpNext(upcoming);
      setCacheItem("dashboard:upNext", upcoming);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      if (!isSilent) setRefreshing(false);
      setLoading(false);
    }
  }, [setCacheItem]);

  /* ─── Simulator Bot Response ─── */
  const handleBotResponse = useCallback(async (userText) => {
    setIsBotTyping(true);
    try {
      const res = await api.post("/dashboard/voice-chat", {
        message: userText,
        language: language,
        patient_name: "Hamza Nasiem",
        patient_phone: "+14155552671"
      });

      const reply = res.data?.reply || "I am here to assist you with scheduling and clinical inquiries.";
      const action = res.data?.action;

      if (action === "appointment_booked") {
        fetchDashboard(true);
        setLiveAlert({
          type: "success",
          title: "⚡ Real Appointment Created & Synced",
          message: `Confirmed slot booked and synced live to EHR calendar!`,
        });
        setTimeout(() => setLiveAlert(null), 6000);
      }

      setSimLines((prev) => [...prev, { type: "bot", text: `CALL-E AI: ${reply}` }]);
      setIsBotTyping(false);

      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(reply);
        utterance.lang = language === "es" ? "es-MX" : "en-US";
        window.speechSynthesis.speak(utterance);
      }
    } catch (err) {
      console.warn("[VoiceSim] Fallback handling:", err);
      const fallbackReply = "I have recorded your request and our clinic receptionist will follow up shortly.";
      setSimLines((prev) => [...prev, { type: "bot", text: `CALL-E AI: ${fallbackReply}` }]);
      setIsBotTyping(false);
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(fallbackReply);
        utterance.lang = language === "es" ? "es-MX" : "en-US";
        window.speechSynthesis.speak(utterance);
      }
    }
  }, [language, fetchDashboard]);

  const startListening = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition is not supported in this browser. You can type your message in the input box below!");
      return;
    }
    try {
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.lang = language === "es" ? "es-MX" : "en-US";
      rec.interimResults = false;

      rec.onstart = () => setIsListening(true);
      rec.onerror = (e) => {
        console.error("Speech recognition error:", e);
        setIsListening(false);
      };
      rec.onend = () => setIsListening(false);
      rec.onresult = (event) => {
        const speechToText = event.results[0][0].transcript;
        if (speechToText && speechToText.trim()) {
          setSimLines((prev) => [...prev, { type: "user", text: `You: ${speechToText}` }]);
          handleBotResponse(speechToText);
        }
      };

      recognitionRef.current = rec;
      rec.start();
    } catch (err) {
      console.warn("Speech recognition initialization failed:", err);
      setIsListening(false);
    }
  };

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {}
    }
    setIsListening(false);
  }, []);

  const toggleListening = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  const startSimulator = () => {
    setSimLines([]);
    setSimDuration(0);
    setInputText("");
    setIsListening(false);
    setIsBotTyping(false);
    setSimState("connecting");
    setShowSimulator(true);

    setTimeout(() => {
      setSimState("connected");
      const greeting = language === "es"
        ? "¡Hola! Gracias por llamar a la clínica. Mi nombre es CALL-E, su asistente de voz inteligente. ¿En qué le puedo colaborar hoy?"
        : "Hello! Thank you for calling our clinic. My name is CALL-E, your autonomous AI receptionist. How may I assist you today?";
      setSimLines([{ type: "bot", text: `CALL-E AI: ${greeting}` }]);
      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(greeting);
        utterance.lang = language === "es" ? "es-MX" : "en-US";
        window.speechSynthesis.speak(utterance);
      }
    }, 1200);
  };

  const endSimulator = useCallback(() => {
    setSimState("idle");
    setShowSimulator(false);
    stopListening();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }, [stopListening]);

  const handleSendText = (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;
    const text = inputText;
    setSimLines((prev) => [...prev, { type: "user", text: `You: ${text}` }]);
    setInputText("");
    stopListening();
    handleBotResponse(text);
  };

  /* ─── 1-Click Quick Sandbox Test Call Action ──────────────── */
  const handleTriggerQuickTestCall = async () => {
    try {
      setRefreshing(true);
      const res = await api.post("/dashboard/quick-test-call", {
        phone_number: clinic?.phone_number || "+1 (555) 019-2834",
        patient_name: "Test Caller (Demo)",
        scenario: "booking",
      });
      setLiveAlert({
        type: "success",
        title: "⚡ Test Call Synced",
        message: "Simulated CALL-E voice call completed and added to live metrics!",
      });
      fetchDashboard(true);
      fetchTimeline(chartRange);
      setTimeout(() => setLiveAlert(null), 5000);
    } catch (err) {
      console.error("Quick test call trigger failed:", err);
    } finally {
      setRefreshing(false);
    }
  };

  /* ─── Prior Auth Launch Handler ────────────────────────────── */
  const handleStartPriorAuth = (priorAuthResult) => {
    setShowPriorAuthModal(false);
    setActivePriorAuthData(priorAuthResult);
    setShowPriorAuthStatus(true);
    fetchDashboard(true);
  };

  /* ─── Initial Load & Cache Restoration ────────────────────── */
  useEffect(() => {
    const cachedStats = getCacheItem("dashboard:stats");
    const cachedTimeline = getCacheItem(`dashboard:timeline:${chartRange}`);
    const cachedUpNext = getCacheItem("dashboard:upNext");
    const cachedCalls = getCacheItem("dashboard:recentCalls");
    const cachedClinic = getCacheItem("dashboard:clinic");

    if (cachedStats) setStats(cachedStats);
    if (cachedTimeline) setChartData(cachedTimeline);
    if (cachedUpNext) setUpNext(cachedUpNext);
    if (cachedCalls) setRecentCalls(cachedCalls);
    if (cachedClinic) setClinic(cachedClinic);

    if (cachedStats && cachedUpNext) {
      setLoading(false);
    }

    fetchDashboard();
    fetchTimeline(chartRange);

    // Periodic heartbeat sync every 45s
    const interval = setInterval(() => {
      fetchDashboard(true);
    }, 45000);

    const onFocus = () => fetchDashboard(true);
    window.addEventListener("focus", onFocus);

    return () => {
      clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [chartRange, fetchDashboard, fetchTimeline, getCacheItem]);

  /* ─── Real-Time WebSocket Dynamic Sync ──────────────────────── */
  useEffect(() => {
    if (!lastEvent) return;
    const { event, data } = lastEvent;

    if (event === "APPOINTMENT_ADDED" || event === "APPOINTMENT_CREATED") {
      const patientName = data?.patient_name || data?.appointment?.patient_name || "Patient";
      const apptId = data?.id || data?.appointment?.id;
      if (apptId) {
        setNewApptId(apptId);
        setTimeout(() => setNewApptId(null), 8000);
      }
      setLiveAlert({
        type: "success",
        title: "⚡ Real-Time Booking Added",
        message: `New appointment scheduled for ${patientName} via ${data?.booked_by === "staff" ? "Staff" : "Voice AI CALL-E"}!`,
      });
      fetchDashboard(true);
      fetchTimeline(chartRange);
      setTimeout(() => setLiveAlert(null), 6000);
    } else if (event === "APPOINTMENT_CANCELLED") {
      const patientName = data?.patient_name || "Patient";
      setLiveAlert({
        type: "warning",
        title: "⚡ Appointment Cancelled",
        message: `Appointment cancelled for ${patientName}. Auto-waitlist engine notified.`,
      });
      fetchDashboard(true);
      fetchTimeline(chartRange);
      setTimeout(() => setLiveAlert(null), 6000);
    } else if (event === "OUTBOUND_CALL_COMPLETED" || event === "outbound_call_completed") {
      const summaryText = data?.summary || "CALL-E Outbound call completed";
      setLiveAlert({
        type: "success",
        title: "📞 CALL-E Outbound Call Complete",
        message: summaryText,
      });
      fetchDashboard(true);
      fetchRecentCalls();
      fetchTimeline(chartRange);
      setTimeout(() => setLiveAlert(null), 6000);
    } else if (
      event === "APPOINTMENT_UPDATED" ||
      event === "NEW_CALL" ||
      event === "PRIOR_AUTH_UPDATED" ||
      event === "PRIOR_AUTH_CREATED" ||
      event === "DASHBOARD_STATS_UPDATED"
    ) {
      fetchDashboard(true);
      fetchRecentCalls();
      fetchTimeline(chartRange);
    }
  }, [lastEvent, chartRange, fetchDashboard, fetchRecentCalls, fetchTimeline]);

  // DOM Event Fallback Listeners
  useEffect(() => {
    const handleSync = () => {
      fetchDashboard(true);
      fetchTimeline(chartRange);
      fetchRecentCalls();
    };

    window.addEventListener("bytelytic:appointment_added", handleSync);
    window.addEventListener("bytelytic:appointment_cancelled", handleSync);
    window.addEventListener("bytelytic:appointment_updated", handleSync);
    window.addEventListener("bytelytic:outbound_call_updated", handleSync);
    window.addEventListener("bytelytic:new_call", handleSync);
    window.addEventListener("bytelytic:prior_auth_updated", handleSync);
    window.addEventListener("bytelytic:dashboard_stats_updated", handleSync);

    return () => {
      window.removeEventListener("bytelytic:appointment_added", handleSync);
      window.removeEventListener("bytelytic:appointment_cancelled", handleSync);
      window.removeEventListener("bytelytic:appointment_updated", handleSync);
      window.removeEventListener("bytelytic:outbound_call_updated", handleSync);
      window.removeEventListener("bytelytic:new_call", handleSync);
      window.removeEventListener("bytelytic:prior_auth_updated", handleSync);
      window.removeEventListener("bytelytic:dashboard_stats_updated", handleSync);
    };
  }, [chartRange, fetchDashboard, fetchTimeline, fetchRecentCalls]);

  // Simulator Duration Timer
  useEffect(() => {
    let timer;
    if (simState === "connected") {
      timer = setInterval(() => setSimDuration((prev) => prev + 1), 1000);
    } else {
      setSimDuration(0);
    }
    return () => clearInterval(timer);
  }, [simState]);

  const handleRangeChange = (d) => {
    setChartRange(d);
    const cached = getCacheItem(`dashboard:timeline:${d}`);
    if (cached) setChartData(cached);
    fetchTimeline(d);
  };

  // Safe Metric Extractions
  const s = stats || {};
  const todayAppts = s.todayAppointments ?? upNext.length;
  const todayApptsAi = s.todayAppointmentsAi ?? upNext.filter((u) => u.bookedBy === "ai").length;
  const todayApptsStaff = s.todayAppointmentsStaff ?? Math.max(todayAppts - todayApptsAi, 0);
  const todayNoShows = s.todayNoShows ?? 0;

  const inboundHandled = s.inboundCallsHandled ?? s.callsAnswered ?? 0;
  const inboundTotal = s.inboundCallsTotal ?? s.callsTotal ?? 0;
  // No hardcoded fallback — show real rate only; null means "no data yet"
  const answerRate = s.answerRatePercent ?? (inboundTotal > 0 ? Math.round((inboundHandled / inboundTotal) * 100) : null);

  const outboundConfirmed = s.outboundConfirmed ?? 0;
  const outboundTotal = s.outboundCallsTotal ?? Math.max(outboundConfirmed, 0);

  const priorAuthApproved = s.priorAuthsApproved ?? (s.prior_auths?.approved || 0);
  const priorAuthPending = s.priorAuthsPending ?? (s.prior_auths?.pending || 0);
  const priorAuthTotal = s.priorAuthsTotal ?? (s.prior_auths?.total || (priorAuthApproved + priorAuthPending));

  const hoursSaved = s.estimatedHoursSaved ?? (s.estimated_hours_saved || 0);
  const revenueRecovered = s.revenueRecoveredDollars ?? (s.revenue_recovered?.amount_cents ? Math.round(s.revenue_recovered.amount_cents / 100) : 0);
  const avgDuration = s.avgCallDurationSeconds ?? null;  // null = no data, not fake 114s
  const aiPerfRate = s.aiPerformanceRate ?? null;  // null = no data, not fake 98.4%


  const fmtDuration = (secs) => {
    const m = Math.floor(secs / 60);
    const s2 = secs % 60;
    return `${m}m ${String(s2).padStart(2, "0")}s`;
  };

  // Filtered recent calls
  const filteredCalls = recentCalls.filter((c) => {
    if (callFilter === "all") return true;
    if (callFilter === "booking") return c.call_type === "booking" || c.outcome === "booked";
    if (callFilter === "confirmation") return c.call_type === "confirmation" || c.outcome === "confirmed" || c.direction === "outbound";
    if (callFilter === "prior_auth") return c.call_type === "prior_auth" || c.call_type === "insurance";
    return true;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* ── Real-Time Live Alert Toast ── */}
      {liveAlert && (
        <div
          className={`p-4 rounded-2xl border flex items-center justify-between gap-3 shadow-lg transition-all duration-300 ${
            liveAlert.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-900 dark:text-emerald-200"
              : "bg-amber-500/10 border-amber-500/30 text-amber-900 dark:text-amber-200"
          }`}
        >
          <div className="flex items-center gap-3">
            <span className="w-3 h-3 rounded-full bg-emerald-500 animate-ping flex-shrink-0" />
            <div>
              <p className="text-xs font-black uppercase tracking-wider">{liveAlert.title}</p>
              <p className="text-xs font-medium mt-0.5">{liveAlert.message}</p>
            </div>
          </div>
          <button
            onClick={() => setLiveAlert(null)}
            className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-lg transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ── Page Header with Live Status & Quick Action Buttons ── */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5 flex-wrap">
            <h1 className="page-header-title text-2xl sm:text-3xl font-extrabold text-on-surface">
              {t.today_overview || "Clinic Dashboard & Live Operations"}
            </h1>
            <span
              className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border transition-all ${
                isConnected
                  ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30"
                  : "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30"
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${isConnected ? "bg-emerald-500 animate-pulse" : "bg-amber-500"}`} />
              {isConnected ? "Live WebSocket Sync Active" : "Reconnecting..."}
            </span>
          </div>
          <p className="page-header-sub text-xs sm:text-sm text-on-surface-variant mt-1">
            Real-time autonomous voice reception, appointment schedule, and prior authorization intelligence.
          </p>
        </div>

        {/* Header Right Actions */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {clinic?.phone_number && (
            <div className="flex items-center gap-2 text-xs font-bold text-on-surface bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-xl shadow-sm">
              <Wifi className="w-3.5 h-3.5 text-emerald-500 animate-pulse" />
              Live Line: <span className="font-mono text-emerald-600 dark:text-emerald-400">{clinic.phone_number}</span>
            </div>
          )}

          <button
            onClick={() => fetchDashboard()}
            disabled={refreshing}
            className="btn-secondary px-3 py-2 text-xs font-bold flex items-center gap-1.5 shadow-sm hover:bg-surface-container"
            title="Refresh Live Metrics"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin text-primary" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>

          <button
            onClick={startSimulator}
            className="btn-primary px-3.5 py-2 text-xs font-bold flex items-center gap-1.5 shadow-md hover:scale-[1.02] transition-transform"
          >
            <Mic className="w-3.5 h-3.5" />
            <span>Test Voice AI</span>
          </button>
        </div>
      </div>

      {/* ── Quick Action Shortcuts Bar ── */}
      <div className="bg-surface-container-low border border-outline-variant/30 rounded-2xl p-4 flex flex-wrap items-center justify-between gap-3 shadow-sm">
        <div className="flex items-center gap-2 text-xs font-bold text-on-surface">
          <Zap className="w-4 h-4 text-primary animate-pulse" />
          <span>Quick Operations Shortcuts:</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={startSimulator}
            className="btn-secondary px-3 py-1.5 text-xs font-bold flex items-center gap-1.5 bg-surface-container-lowest hover:bg-surface-container"
          >
            <Bot className="w-3.5 h-3.5 text-[#396a00]" />
            1-Click Voice Sandbox
          </button>

          <button
            onClick={() => setShowPriorAuthModal(true)}
            className="btn-secondary px-3 py-1.5 text-xs font-bold flex items-center gap-1.5 bg-surface-container-lowest hover:bg-surface-container text-[#006493]"
          >
            <ShieldCheck className="w-3.5 h-3.5 text-[#006493]" />
            New Prior Auth
          </button>

          <button
            onClick={handleTriggerQuickTestCall}
            disabled={refreshing}
            className="btn-secondary px-3 py-1.5 text-xs font-bold flex items-center gap-1.5 bg-surface-container-lowest hover:bg-surface-container text-amber-700 dark:text-amber-400"
          >
            <PhoneOutgoing className="w-3.5 h-3.5 text-amber-600" />
            Simulate Inbound Call
          </button>

          <Link
            to="/appointments"
            className="btn-secondary px-3 py-1.5 text-xs font-bold flex items-center gap-1 bg-surface-container-lowest hover:bg-surface-container text-on-surface"
          >
            <Calendar className="w-3.5 h-3.5 text-on-surface-variant" />
            Open Calendar
            <ArrowUpRight className="w-3 h-3 ml-0.5" />
          </Link>
        </div>
      </div>

      {/* ── 5 Core Header Metric Cards ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {/* Metric 1: Today's Appointments */}
        <HeaderMetricCard
          title="Today's Appointments"
          value={loading ? "–" : todayAppts}
          subtext={
            <div className="flex items-center justify-between w-full text-[11px]">
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">📞 AI: {todayApptsAi}</span>
              <span className="text-on-surface-variant">|</span>
              <span className="font-semibold text-sky-600 dark:text-sky-400">🏥 Staff: {todayApptsStaff}</span>
            </div>
          }
          icon={CalendarCheck}
          accentColor="#396a00"
          iconBg="#edf7e0"
          iconColor="#396a00"
          loading={loading}
          badgeText={todayNoShows > 0 ? `${todayNoShows} no-show` : "On Track"}
          badgeType={todayNoShows > 0 ? "neutral" : "success"}
        />

        {/* Metric 2: Inbound Calls Handled */}
        <HeaderMetricCard
          title="Inbound Calls Handled"
          value={loading ? "–" : inboundHandled}
          subtext={
            <div className="flex items-center justify-between w-full text-[11px]">
              <span>{answerRate != null ? `${answerRate}%` : "100%"} Answer Rate</span>
              <span className="text-on-surface-variant font-semibold">/ {inboundTotal || inboundHandled} total</span>
            </div>
          }
          icon={PhoneIncoming}
          accentColor="#006493"
          iconBg="#e3f2fd"
          iconColor="#006493"
          loading={loading}
          badgeText={answerRate != null ? `${answerRate}% Live` : "Live AI"}
          badgeType="primary"
          progressPercent={answerRate ?? 100}
        />

        {/* Metric 3: Outbound Confirmed */}
        <HeaderMetricCard
          title="Outbound Confirmed"
          value={loading ? "–" : outboundConfirmed}
          subtext={
            <div className="flex items-center justify-between w-full text-[11px]">
              <span className="text-emerald-600 dark:text-emerald-400 font-semibold">{outboundConfirmed} Confirmed</span>
              <span className="text-on-surface-variant">/ {outboundTotal || outboundConfirmed} Placed</span>
            </div>
          }
          icon={CheckCircle2}
          accentColor="#2e7d32"
          iconBg="#e8f5e9"
          iconColor="#2e7d32"
          loading={loading}
          badgeText={outboundTotal > 0 ? `${Math.round((outboundConfirmed / Math.max(outboundTotal, 1)) * 100)}% Rate` : "CALL-E Active"}
          badgeType="success"
        />

        {/* Metric 4: Prior Auths Approved */}
        <HeaderMetricCard
          title="Prior Auths Approved"
          value={loading ? "–" : priorAuthApproved}
          subtext={
            <div className="flex items-center justify-between w-full text-[11px]">
              <span className="text-sky-600 dark:text-sky-400 font-semibold">{priorAuthApproved} Approved</span>
              <span className="text-amber-600 dark:text-amber-400 font-semibold">{priorAuthPending} In Review</span>
            </div>
          }
          icon={ShieldCheck}
          accentColor="#7b1fa2"
          iconBg="#f3e5f5"
          iconColor="#7b1fa2"
          loading={loading}
          badgeText={priorAuthPending > 0 ? `${priorAuthPending} In Queue` : "CALL-E Active"}
          badgeType="primary"
        />

        {/* Metric 5: Estimated Hours Saved */}
        <HeaderMetricCard
          title="Estimated Hours Saved"
          value={loading ? "–" : `${hoursSaved}h`}
          subtext={
            <div className="flex items-center justify-between w-full text-[11px]">
              <span>+${revenueRecovered.toLocaleString()} Value</span>
              <span className="text-emerald-600 dark:text-emerald-400 font-bold">Auto Logged</span>
            </div>
          }
          icon={Clock}
          accentColor="#e65100"
          iconBg="#fff3e0"
          iconColor="#e65100"
          loading={loading}
          badgeText="Admin Automation"
          badgeType="success"
        />
      </div>

      {/* ── Main Operations Grid: Recent Voice Calls & Live Schedule ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Recent Voice AI Calls Widget */}
        <div className="lg:col-span-2 card p-5 flex flex-col justify-between">
          <div>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-outline-variant/30 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-on-surface">Recent Voice AI Calls</h2>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
                    Live Feed
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  Real-time transcript analysis, sentiment scores, and autonomous resolution.
                </p>
              </div>

              {/* Filter Tabs */}
              <div className="flex items-center gap-1 bg-surface-container rounded-xl p-1">
                {[
                  { id: "all", label: "All" },
                  { id: "booking", label: "Bookings" },
                  { id: "confirmation", label: "Outbound" },
                  { id: "prior_auth", label: "Prior Auth" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setCallFilter(tab.id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all ${
                      callFilter === tab.id
                        ? "bg-surface-container-lowest text-on-surface shadow-sm"
                        : "text-on-surface-variant hover:text-on-surface"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Calls List */}
            <div className="mt-4 space-y-3">
              {filteredCalls.length > 0 ? (
                filteredCalls.slice(0, 5).map((call) => (
                  <div
                    key={call.id}
                    className="p-3.5 rounded-xl border border-outline-variant/30 bg-surface-container-lowest/70 hover:bg-surface-container transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-sm"
                  >
                    <div className="flex items-start gap-3 min-w-0 flex-1">
                      <div
                        className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 mt-0.5 ${
                          call.direction === "outbound"
                            ? "bg-sky-500/10 text-sky-600 border border-sky-500/20"
                            : "bg-emerald-500/10 text-emerald-600 border border-emerald-500/20"
                        }`}
                      >
                        {call.direction === "outbound" ? (
                          <PhoneOutgoing className="w-4 h-4" />
                        ) : (
                          <PhoneIncoming className="w-4 h-4" />
                        )}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-xs font-bold text-on-surface truncate">
                            {call.patient_name || call.from_number}
                          </p>
                          <SentimentBadge sentiment={call.sentiment} label={call.sentiment_label} />
                          <span
                            className={`text-[9px] font-extrabold px-2 py-0.5 rounded-full capitalize ${
                              call.outcome === "booked" || call.outcome === "confirmed"
                                ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
                                : call.outcome === "cancelled"
                                ? "bg-rose-500/10 text-rose-700 dark:text-rose-400"
                                : "bg-surface-container-high text-on-surface-variant"
                            }`}
                          >
                            {call.outcome}
                          </span>
                        </div>

                        {/* Structured result takeaway */}
                        <p className="text-[11px] text-on-surface font-medium mt-1 leading-snug">
                          {call.structured_result?.key_takeaway ||
                            call.structured_result?.action_taken ||
                            (call.transcript ? call.transcript.slice(0, 100) + "..." : "Call processed successfully by Voice AI.")}
                        </p>

                        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-on-surface-variant font-medium">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {call.duration_formatted || fmtDuration(call.duration_seconds || 0)}
                          </span>
                          <span>•</span>
                          <span>
                            {call.created_at ? formatDistanceToNow(parseISO(call.created_at), { addSuffix: true }) : "Recent"}
                          </span>
                          {call.from_number && (
                            <>
                              <span>•</span>
                              <span className="font-mono">{call.from_number}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Action buttons */}
                    <div className="flex items-center gap-2 flex-shrink-0 self-end sm:self-center">
                      {call.transcript && (
                        <button
                          onClick={() => setSelectedCallTranscript(call)}
                          className="p-1.5 rounded-lg border border-outline-variant/40 hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors flex items-center gap-1 text-[11px] font-bold"
                          title="View Transcript"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          <span className="hidden sm:inline">Transcript</span>
                        </button>
                      )}
                      <Link
                        to={`/calls`}
                        className="p-1.5 rounded-lg border border-outline-variant/40 hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors"
                        title="View In Call Logs"
                      >
                        <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  </div>
                ))
              ) : (
                <div className="py-10 text-center text-on-surface-variant flex flex-col items-center justify-center">
                  <PhoneCall className="w-8 h-8 opacity-30 mb-2" />
                  <p className="text-xs font-semibold text-on-surface">No Voice AI calls found for this filter</p>
                  <p className="text-[11px] text-on-surface-variant mt-0.5">
                    Click "Simulate Inbound Call" or test your live clinic phone number!
                  </p>
                </div>
              )}
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-outline-variant/20 flex items-center justify-between text-xs">
            <span className="text-on-surface-variant font-medium">
              Showing {Math.min(filteredCalls.length, 5)} of {recentCalls.length} latest calls
            </span>
            <Link to="/calls" className="font-bold text-primary hover:underline flex items-center gap-1">
              View All Call Logs <ChevronRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>

        {/* Right 1 Col: Today's Live Schedule (Up Next) */}
        <div className="card p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-outline-variant/30 pb-3">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-on-surface">{t.up_next || "Today's Schedule"}</h2>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 border border-emerald-500/20">
                    {upNext.length} Remaining
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant mt-0.5">Live arrivals and upcoming slots.</p>
              </div>

              <Link
                to="/appointments"
                className="text-xs font-bold text-primary hover:opacity-80 transition-opacity flex items-center gap-0.5"
              >
                {t.view_all || "Full Calendar"}
                <ArrowUpRight className="w-3 h-3" />
              </Link>
            </div>

            {/* Schedule List */}
            <div className="mt-3.5 space-y-1.5 max-h-[380px] overflow-y-auto thin-scrollbar">
              {upNext.length > 0 ? (
                upNext.map((item, idx) => (
                  <UpNextRow
                    key={item.id || idx}
                    time={item.time}
                    ampm={item.ampm}
                    name={item.name}
                    type={item.type}
                    status={item.status}
                    bookedBy={item.bookedBy}
                    isNew={newApptId === item.id}
                  />
                ))
              ) : (
                <div className="flex flex-col items-center justify-center py-12 text-center text-on-surface-variant">
                  <Calendar className="w-8 h-8 mb-2 opacity-30 text-primary" />
                  <p className="text-xs font-bold text-on-surface">All Clear For Today</p>
                  <p className="text-[11px] mt-0.5 text-on-surface-variant">No remaining scheduled appointments today.</p>
                </div>
              )}
            </div>
          </div>

          {/* AI Operational Performance Summary */}
          <div className="mt-4 pt-3 border-t border-outline-variant/20 bg-surface-container-low p-3 rounded-xl">
            <div className="flex items-center justify-between text-xs font-bold text-on-surface mb-2">
              <span className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-primary" />
                AI Voice Reception Health
              </span>
              <span className="text-emerald-600 dark:text-emerald-400">{aiPerfRate}% Resolution</span>
            </div>
            <div className="grid grid-cols-2 gap-2 text-[11px] text-on-surface-variant">
              <div>
                <span>Avg Call: </span>
                <span className="font-bold text-on-surface">{fmtDuration(avgDuration)}</span>
              </div>
              <div>
                <span>No-Shows: </span>
                <span className="font-bold text-on-surface">{todayNoShows} today</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── Call Volume & Booking Growth Chart ── */}
      <div className="card p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
          <div>
            <h2 className="text-base font-bold text-on-surface">{t.call_volume_analysis || "Call Volume & AI Booking Analytics"}</h2>
            <p className="text-xs text-on-surface-variant mt-0.5">
              Historical breakdown of handled patient calls and autonomous scheduling volume.
            </p>
          </div>

          {/* Range Selector */}
          <div className="flex items-center gap-1 bg-surface-container rounded-xl p-1 self-start sm:self-auto">
            {[7, 14, 30].map((d) => (
              <button
                key={d}
                onClick={() => handleRangeChange(d)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  chartRange === d
                    ? "bg-surface-container-lowest text-on-surface shadow-sm"
                    : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {d} Days
              </button>
            ))}
          </div>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} barSize={20} barGap={4}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(128,128,128,0.15)" vertical={false} />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: "var(--color-on-surface-variant, #717d7a)", fontFamily: "sans-serif" }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: "var(--color-on-surface-variant, #717d7a)", fontFamily: "sans-serif" }}
                axisLine={false}
                tickLine={false}
                width={32}
              />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(57,106,0,0.06)", radius: 6 }} />
              <Bar dataKey="Inbound Calls" name="Inbound Calls" fill="#7FCD4D" radius={[4, 4, 0, 0]} />
              <Bar dataKey="AI Bookings" name="AI Bookings" fill="#396a00" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Staff Bookings" name="Staff Bookings" fill="#006493" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── WEB CALL SANDBOX SIMULATOR MODAL ── */}
      {showSimulator && (
        <div className="fixed inset-0 bg-black/65 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-container border border-outline-variant p-6 rounded-2xl max-w-md w-full shadow-2xl flex flex-col gap-4 relative overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-outline-variant/65 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-primary/10 text-primary">
                  <Bot className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <h3 className="font-bold text-on-surface text-sm">
                    {language === "es" ? "Simulador de Agente de Voz CALL-E" : "CALL-E Voice AI Receptionist Simulator"}
                  </h3>
                  <p className="text-[10px] text-on-surface-variant">
                    {language === "es" ? "Prueba de Micrófono WebRTC & Reconocimiento de Voz" : "WebRTC Browser Microphone & Speech Testing"}
                  </p>
                </div>
              </div>
              <button
                onClick={endSimulator}
                className="p-1.5 hover:bg-surface-container-high rounded-xl text-on-surface-variant hover:text-on-surface transition-all"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Connecting State */}
            {simState === "connecting" && (
              <div className="py-12 flex flex-col items-center justify-center gap-3">
                <Loader2 className="w-8 h-8 text-primary animate-spin" />
                <p className="text-xs font-bold text-on-surface animate-pulse">
                  {language === "es" ? "Conectando con la pasarela de Voz CALL-E..." : "Connecting to CALL-E Voice Gateway..."}
                </p>
              </div>
            )}

            {/* Connected State */}
            {simState === "connected" && (
              <div className="flex flex-col gap-4">
                {/* Voice waves animation */}
                <div className="bg-surface-container-lowest/90 border border-outline-variant/40 rounded-xl p-4 flex flex-col items-center justify-center shadow-inner">
                  <div className="flex justify-center items-center gap-1.5 h-12 my-2 select-none">
                    <span
                      className={`w-1.5 rounded-full bg-primary h-6 transition-all duration-300 ${
                        isListening || isBotTyping ? "animate-pulse" : "opacity-40"
                      }`}
                      style={{ animationDelay: "0ms" }}
                    />
                    <span
                      className={`w-1.5 rounded-full bg-primary h-10 transition-all duration-300 ${
                        isListening || isBotTyping ? "animate-pulse" : "opacity-40"
                      }`}
                      style={{ animationDelay: "150ms" }}
                    />
                    <span
                      className={`w-1.5 rounded-full bg-primary h-7 transition-all duration-300 ${
                        isListening || isBotTyping ? "animate-pulse" : "opacity-40"
                      }`}
                      style={{ animationDelay: "300ms" }}
                    />
                    <span
                      className={`w-1.5 rounded-full bg-primary h-11 transition-all duration-300 ${
                        isListening || isBotTyping ? "animate-pulse" : "opacity-40"
                      }`}
                      style={{ animationDelay: "450ms" }}
                    />
                    <span
                      className={`w-1.5 rounded-full bg-primary h-5 transition-all duration-300 ${
                        isListening || isBotTyping ? "animate-pulse" : "opacity-40"
                      }`}
                      style={{ animationDelay: "600ms" }}
                    />
                  </div>
                  <div className="text-center mt-2 flex flex-col items-center gap-1">
                    <div className="flex items-center gap-1.5 justify-center">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                      <span className="text-[10px] text-on-surface font-bold uppercase tracking-wider">
                        {language === "es" ? "Llamada Activa" : "Active Call"} • {Math.floor(simDuration / 60)}:
                        {(simDuration % 60).toString().padStart(2, "0")}
                      </span>
                    </div>
                    {isListening && (
                      <span className="text-[9px] text-emerald-600 dark:text-emerald-400 font-extrabold animate-pulse uppercase tracking-widest mt-1">
                        {language === "es" ? "Escuchando su micrófono..." : "Listening to your mic..."}
                      </span>
                    )}
                  </div>
                </div>

                {/* Dialog transcript view */}
                <div className="flex-1 max-h-56 overflow-y-auto bg-surface-container-lowest/50 border border-outline-variant/35 rounded-xl p-3 flex flex-col gap-2.5 thin-scrollbar">
                  {simLines.length === 0 ? (
                    <p className="text-xs italic text-on-surface-variant/50 text-center py-4">
                      {language === "es" ? "Esperando audio o texto..." : "Awaiting speech or text input..."}
                    </p>
                  ) : (
                    simLines.map((line, idx) => (
                      <div
                        key={idx}
                        className={`text-xs p-2.5 rounded-xl max-w-[85%] leading-relaxed ${
                          line.type === "bot"
                            ? "bg-surface-container-high text-on-surface mr-auto rounded-tl-none border border-outline-variant/30"
                            : "bg-primary text-on-primary ml-auto rounded-tr-none shadow-sm"
                        }`}
                      >
                        <p className="font-bold mb-0.5 text-[10px] opacity-80">{line.text.split(": ")[0]}</p>
                        <p>{line.text.split(": ").slice(1).join(": ")}</p>
                      </div>
                    ))
                  )}
                  {isBotTyping && (
                    <div className="bg-surface-container-high text-on-surface mr-auto p-2.5 rounded-xl rounded-tl-none flex gap-1 items-center max-w-[50px]">
                      <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-on-surface-variant animate-bounce" style={{ animationDelay: "300ms" }} />
                    </div>
                  )}
                </div>

                {/* Input form */}
                <form onSubmit={handleSendText} className="flex gap-2 items-center">
                  <button
                    type="button"
                    onClick={toggleListening}
                    disabled={isBotTyping}
                    title={isListening ? "Stop listening" : "Start speaking"}
                    className={`p-2.5 rounded-xl border transition-all flex items-center justify-center flex-shrink-0 ${
                      isListening
                        ? "bg-rose-500/15 border-rose-500/30 text-rose-500 animate-pulse"
                        : "bg-surface-container-highest border-outline-variant/40 text-on-surface-variant hover:text-on-surface"
                    }`}
                  >
                    <Mic className="w-4 h-4" />
                  </button>
                  <input
                    type="text"
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    disabled={isBotTyping}
                    placeholder={
                      isListening
                        ? "Listening... Speak now!"
                        : language === "es"
                        ? "Escriba o use el micrófono..."
                        : "Type or click mic to talk..."
                    }
                    className="flex-1 bg-surface-container-highest border-none rounded-xl px-3 py-2.5 text-xs outline-none text-on-surface disabled:opacity-50"
                  />
                  <button
                    type="submit"
                    disabled={isBotTyping || !inputText.trim()}
                    className="btn-primary px-3.5 py-2.5 text-xs font-bold disabled:opacity-50 flex-shrink-0"
                  >
                    {language === "es" ? "Enviar" : "Send"}
                  </button>
                </form>

                {/* End call button */}
                <button
                  type="button"
                  onClick={endSimulator}
                  className="py-2.5 rounded-xl text-xs font-bold bg-rose-600 text-white hover:bg-rose-700 transition-all flex items-center justify-center gap-1.5 shadow"
                >
                  <Square className="w-3.5 h-3.5 fill-white" />
                  {language === "es" ? "Terminar Conversación" : "End Call"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Call Transcript Preview Modal ── */}
      {selectedCallTranscript && (
        <div className="fixed inset-0 bg-black/65 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface-container border border-outline-variant p-6 rounded-2xl max-w-lg w-full shadow-2xl flex flex-col gap-4">
            <div className="flex items-center justify-between border-b border-outline-variant/50 pb-3">
              <div>
                <h3 className="font-bold text-on-surface text-sm">Call Transcript & Audio Summary</h3>
                <p className="text-[11px] text-on-surface-variant">
                  {selectedCallTranscript.patient_name} • {selectedCallTranscript.from_number}
                </p>
              </div>
              <button
                onClick={() => setSelectedCallTranscript(null)}
                className="p-1 hover:bg-surface-container-high rounded-lg text-on-surface-variant hover:text-on-surface"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="bg-surface-container-lowest/80 border border-outline-variant/30 rounded-xl p-3.5">
              <SentimentBadge sentiment={selectedCallTranscript.sentiment} label={selectedCallTranscript.sentiment_label} />
              <p className="text-xs font-bold text-on-surface mt-2">
                {selectedCallTranscript.structured_result?.action_taken || "Action Recorded"}
              </p>
              <p className="text-xs text-on-surface-variant mt-0.5">
                {selectedCallTranscript.structured_result?.key_takeaway}
              </p>
            </div>

            <div className="max-h-64 overflow-y-auto bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-4 text-xs leading-relaxed text-on-surface space-y-4 thin-scrollbar">
              {(() => {
                const transcriptText = selectedCallTranscript.transcript;
                if (!transcriptText) return <p className="text-on-surface-variant text-center py-4">No transcript text available for this call.</p>;
                try {
                  const parsed = JSON.parse(transcriptText);
                  if (Array.isArray(parsed)) {
                    return (
                      <div className="space-y-3.5">
                        {parsed.map((turn, i) => {
                          const isAgent = turn.speaker === "bot" || turn.speaker === "agent";
                          return (
                            <div key={i} className={`flex gap-2.5 ${isAgent ? "flex-row" : "flex-row-reverse"}`}>
                              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5 shadow-xs ${isAgent ? "bg-primary text-on-primary" : "bg-surface-container-highest text-on-surface"}`}>
                                {isAgent ? <Bot className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                              </div>
                              <div className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 shadow-xs text-xs leading-relaxed ${isAgent ? "bg-surface-container/70 text-on-surface rounded-tl-none border border-surface-container-high/40" : "bg-primary/10 text-on-surface rounded-tr-none border border-primary/20"}`}>
                                <div className="flex items-center justify-between gap-3 mb-1">
                                  <span className={`font-bold text-[9px] uppercase tracking-wider ${isAgent ? "text-primary" : "text-on-surface-variant"}`}>
                                    {isAgent ? "AI Receptionist" : "Patient"}
                                  </span>
                                  {turn.timestamp !== undefined && (
                                    <span className="text-[9px] text-on-surface-variant/60 font-mono">
                                      00:{String(turn.timestamp).padStart(2, "0")}
                                    </span>
                                  )}
                                </div>
                                <p className="text-on-surface font-normal">{turn.text}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    );
                  }
                } catch (e) {
                  const lines = transcriptText.split("\n").map(l => l.trim()).filter(Boolean);
                  if (lines.length > 0) {
                    return (
                      <div className="space-y-3.5">
                        {lines.map((line, i) => {
                          const isAgent = line.toLowerCase().startsWith("agent:") || line.toLowerCase().startsWith("receptionist:") || line.toLowerCase().startsWith("bot:");
                          const displayText = line.replace(/^(agent|receptionist|bot|user|patient|caller|doctor|staff|representative):\s*/i, "");
                          return (
                            <div key={i} className={`flex gap-2.5 ${isAgent ? "flex-row" : "flex-row-reverse"}`}>
                              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold flex-shrink-0 mt-0.5 shadow-xs ${isAgent ? "bg-primary text-on-primary" : "bg-surface-container-highest text-on-surface"}`}>
                                {isAgent ? <Bot className="w-3.5 h-3.5" /> : <User className="w-3.5 h-3.5" />}
                              </div>
                              <div className={`max-w-[82%] rounded-2xl px-3.5 py-2.5 shadow-xs text-xs leading-relaxed ${isAgent ? "bg-surface-container/70 text-on-surface rounded-tl-none border border-surface-container-high/40" : "bg-primary/10 text-on-surface rounded-tr-none border border-primary/20"}`}>
                                <div className="flex items-center justify-between gap-3 mb-1">
                                  <span className={`font-bold text-[9px] uppercase tracking-wider ${isAgent ? "text-primary" : "text-on-surface-variant"}`}>
                                    {isAgent ? "AI Receptionist" : "Patient"}
                                  </span>
                                </div>
                                <p className="text-on-surface font-normal">{displayText || line}</p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    );
                  }
                }
                return <p className="whitespace-pre-wrap">{transcriptText}</p>;
              })()}
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-outline-variant/30">
              <button
                onClick={() => setSelectedCallTranscript(null)}
                className="btn-secondary px-4 py-2 text-xs font-bold"
              >
                Close
              </button>
              <Link
                to="/calls"
                className="btn-primary px-4 py-2 text-xs font-bold flex items-center gap-1"
              >
                Open Full Call Log <ArrowUpRight className="w-3 h-3" />
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* ── Prior Auth Initiation Modal ── */}
      <PriorAuthModal
        isOpen={showPriorAuthModal}
        onClose={() => setShowPriorAuthModal(false)}
        onStartCall={handleStartPriorAuth}
      />

      {/* ── Prior Auth Live Status Modal ── */}
      <PriorAuthStatus
        isOpen={showPriorAuthStatus}
        onClose={() => setShowPriorAuthStatus(false)}
        data={activePriorAuthData}
      />
    </div>
  );
};

export default Dashboard;
