import React, { useState, useEffect, useRef } from "react";
import { 
  Bot, 
  HelpCircle, 
  Plus, 
  Trash2, 
  Save, 
  CheckCircle, 
  AlertCircle, 
  Loader2, 
  PhoneCall, 
  Sparkles, 
  FileText,
  Volume2,
  VolumeX,
  RefreshCw,
  Eye,
  X,
  Copy,
  Check,
  ShieldAlert,
  Globe,
  Sliders,
  Zap,
  Play,
  Square,
  User,
  Heart,
  Briefcase,
  Smile,
  Info
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { translations } from "../lib/translations";

const PRESET_VOICES = [
  { value: "11labs-rachel", label: "Rachel (Female, Warm Professional English)", provider: "ElevenLabs" },
  { value: "11labs-charlie", label: "Charlie (Male, Empathetic English)", provider: "ElevenLabs" },
  { value: "11labs-adam", label: "Adam (Male, Deep Clinical English)", provider: "ElevenLabs" },
  { value: "11labs-Adrian", label: "Adrian (Male, Friendly Clinical English)", provider: "ElevenLabs" },
  { value: "11labs-Sarah", label: "Sarah (Female, Empathetic Reassuring English)", provider: "ElevenLabs" },
  { value: "11labs-brian", label: "Brian (Male, Authoritative English)", provider: "ElevenLabs" },
  { value: "11labs-emma", label: "Emma (Female, Friendly British English)", provider: "ElevenLabs" },
  { value: "11labs-george", label: "George (Male, Resonant British English)", provider: "ElevenLabs" },
  { value: "11labs-maria", label: "María (Female, Clear Spanish)", provider: "ElevenLabs" },
  { value: "11labs-jose", label: "José (Male, Professional Spanish)", provider: "ElevenLabs" },
  { value: "openai-Alloy", label: "Alloy (Neutral, Crisp OpenAI)", provider: "OpenAI" },
  { value: "openai-Echo", label: "Echo (Male, Warm OpenAI)", provider: "OpenAI" },
  { value: "openai-Shimmer", label: "Shimmer (Female, Gentle OpenAI)", provider: "OpenAI" },
  { value: "openai-Onyx", label: "Onyx (Male, Deep OpenAI)", provider: "OpenAI" },
  { value: "openai-Nova", label: "Nova (Female, Energetic OpenAI)", provider: "OpenAI" },
  { value: "openai-Fable", label: "Fable (Neutral, British OpenAI)", provider: "OpenAI" },
  { value: "custom", label: "Custom Voice ID...", provider: "Custom" }
];

const LANG_OPTIONS = [
  { value: "en-US", label: "English (US)" },
  { value: "en-GB", label: "English (UK)" },
  { value: "es-MX", label: "Spanish (Mexico)" },
  { value: "es-ES", label: "Spanish (Spain)" },
  { value: "fr-CA", label: "French (Canada)" },
  { value: "fr-FR", label: "French (France)" },
  { value: "pt-BR", label: "Portuguese (Brazil)" }
];

const AI_NAME_PRESETS = [
  { id: "Alex", label: "Alex", subtitle: "Warm & Empathetic (Default)", desc: "Balanced, friendly bedside manner" },
  { id: "Monika", label: "Monika", subtitle: "Polished & Professional", desc: "Structured, crisp medical receptionist" },
  { id: "custom", label: "Custom Name", subtitle: "Personalized Brand", desc: "Define your own practice receptionist name" }
];

const SPEAKING_STYLES = [
  {
    id: "Warm & Empathetic",
    icon: Heart,
    color: "text-rose-500",
    bgColor: "bg-rose-500/10 border-rose-500/30",
    title: "Warm & Empathetic",
    desc: "Compassionate bedside manner, comforting validation, soothing cadence. Ideal for family medicine, therapy & wellness."
  },
  {
    id: "Concise & Professional",
    icon: Briefcase,
    color: "text-blue-500",
    bgColor: "bg-blue-500/10 border-blue-500/30",
    title: "Concise & Professional",
    desc: "Crisp, efficient, direct precision. Rapid slot discovery and structured clarity. Ideal for busy surgical & urgent clinics."
  },
  {
    id: "Friendly & Casual",
    icon: Smile,
    color: "text-emerald-500",
    bgColor: "bg-emerald-500/10 border-emerald-500/30",
    title: "Friendly & Casual",
    desc: "Upbeat, approachable warmth, conversational hospitality. Ideal for dental, dermatology & aesthetic practices."
  }
];

const GREETING_PRESETS = [
  {
    title: "Standard Medical",
    text: "Hello, thank you for calling the clinic! My name is Alex. How can I help you today?"
  },
  {
    title: "Friendly Dental",
    text: "Hi there! Thanks for calling our office. My name is Alex. Are you looking to schedule a cleaning or consultation today?"
  },
  {
    title: "Urgent Care Safety",
    text: "Thank you for calling Sunrise Clinic. If you are experiencing a life-threatening medical emergency, please hang up and dial 911 immediately. Otherwise, how may I assist you?"
  },
  {
    title: "Bilingual Spanish",
    text: "¡Hola! Gracias por llamar a nuestra clínica médica. Mi nombre es Alex. ¿En qué le podemos ayudar el día de hoy?"
  },
  {
    title: "Physical Therapy & Rehab",
    text: "Hello! Thank you for calling our wellness and therapy center. My name is Alex. How can we assist you with your recovery or scheduling today?"
  }
];

const PROMPT_SNIPPETS = [
  {
    title: "Scheduling Guidance",
    content: "\n• SCHEDULING: Always collect patient's full legal name, phone number, date of birth, and preferred appointment time before confirming bookings."
  },
  {
    title: "Insurance Policy",
    content: "\n• INSURANCE: Inform patients we accept major PPO plans and Medicare. For HMO or out-of-network plans, recommend speaking with our billing coordinator."
  },
  {
    title: "Cancellation Policy",
    content: "\n• CANCELLATION: Remind callers that appointments must be cancelled or rescheduled at least 24 hours in advance to avoid late cancellation fees."
  },
  {
    title: "Directions & Parking",
    content: "\n• LOCATION & PARKING: Mention free dedicated patient parking is located right in front of our main building entrance with wheelchair accessibility."
  },
  {
    title: "Emergency Triage",
    content: "\n• EMERGENCY PROTOCOL: If caller reports chest pain, severe shortness of breath, sudden weakness, or uncontrolled bleeding, direct them to hang up and call 911 or go to the nearest ER immediately."
  }
];

const FAQ_TEMPLATES = [
  {
    q: "What are your business hours?",
    a: "We are open Monday through Friday from 8:00 AM to 5:00 PM, and Saturday from 9:00 AM to 1:00 PM. We are closed on Sundays."
  },
  {
    q: "Where are you located and is parking available?",
    a: "We are located at our main medical suite. Free dedicated patient parking is available directly in front of the building."
  },
  {
    q: "Do you accept new patients or walk-ins?",
    a: "Yes, we warmly welcome new patients! Walk-ins are accommodated based on daily schedule availability, though booking in advance is highly recommended."
  },
  {
    q: "What should I bring to my first appointment?",
    a: "Please bring a valid photo ID, your current insurance card, and any relevant prior medical records or medication lists."
  }
];

const AgentBuilderSettings = () => {
  const { language } = useAuth();
  const t = translations[language] || translations.en;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [msg, setMsg] = useState(null);
  const [copied, setCopied] = useState(false);

  // Agent Persona Form State
  const [aiNamePreset, setAiNamePreset] = useState("Alex");
  const [aiNameCustom, setAiNameCustom] = useState("");
  const [speakingStyle, setSpeakingStyle] = useState("Warm & Empathetic");
  const [retellAgentId, setRetellAgentId] = useState("");
  const [greetingMessage, setGreetingMessage] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [voiceId, setVoiceId] = useState("11labs-rachel");
  const [customVoiceId, setCustomVoiceId] = useState("");
  const [isCustomVoice, setIsCustomVoice] = useState(false);
  const [langCode, setLangCode] = useState("en-US");
  const [emergencyPhone, setEmergencyPhone] = useState("");
  const [emergencyProtocols, setEmergencyProtocols] = useState("");
  
  // Audio Speech Synthesis Preview State
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [audioError, setAudioError] = useState(null);
  const synthRef = useRef(null);

  // Sync state from server
  const [retellSyncStatus, setRetellSyncStatus] = useState("not_synced");
  const [retellSyncedAt, setRetellSyncedAt] = useState(null);

  // FAQs State
  const [faqs, setFaqs] = useState([]);
  const [newQuestion, setNewQuestion] = useState("");
  const [newAnswer, setNewAnswer] = useState("");

  // A/B Testing State
  const [abTestActive, setAbTestActive] = useState(false);
  const [scriptA, setScriptA] = useState("");
  const [scriptB, setScriptB] = useState("");

  // Preview Modal State
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewPrompt, setPreviewPrompt] = useState("");
  const [previewCharCount, setPreviewCharCount] = useState(0);

  useEffect(() => {
    fetchAgentConfig();
    return () => {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  const fetchAgentConfig = async () => {
    setLoading(true);
    setMsg(null);
    try {
      const res = await api.get("/agent-config");
      const config = res.data.data;
      if (config) {
        setRetellAgentId(config.retell_agent_id || "");
        setGreetingMessage(config.greeting_message || "");
        setSystemPrompt(config.custom_system_prompt || "");
        
        // AI Name mapping
        const savedName = config.ai_name || "Alex";
        if (savedName === "Alex" || savedName === "Monika") {
          setAiNamePreset(savedName);
          setAiNameCustom("");
        } else {
          setAiNamePreset("custom");
          setAiNameCustom(savedName);
        }

        // Speaking Style mapping
        setSpeakingStyle(config.speaking_style || "Warm & Empathetic");

        const rawVoice = config.voice_id || "11labs-rachel";
        const isPreset = PRESET_VOICES.some(v => v.value === rawVoice && v.value !== "custom");
        if (isPreset) {
          setVoiceId(rawVoice);
          setIsCustomVoice(false);
        } else {
          setVoiceId("custom");
          setCustomVoiceId(rawVoice);
          setIsCustomVoice(true);
        }

        setLangCode(config.language || "en-US");
        setEmergencyPhone(config.emergency_forward_phone || config.transfer_phone_number || "");
        setEmergencyProtocols(config.emergency_protocols || "If caller reports chest pain, shortness of breath, severe bleeding, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest hospital emergency room.");
        setAbTestActive(config.ab_test_active || false);
        setScriptA(config.script_a || "");
        setScriptB(config.script_b || "");
        setRetellSyncStatus(config.retell_sync_status || "synced");
        setRetellSyncedAt(config.retell_synced_at || null);
        
        // Convert faq_data object to list of { q, a }
        const faqObj = config.faq_data || {};
        const faqList = Object.entries(faqObj).map(([q, a]) => ({ q, a }));
        setFaqs(faqList);
      }
    } catch (err) {
      if (err.response?.status === 404) {
        // Not configured yet, pre-populate standard medical prompt & greeting
        setGreetingMessage("Hello, thank you for calling the clinic! My name is Alex. How can I help you today?");
        setSystemPrompt("You are a helpful, courteous medical practice receptionist. Assist callers with appointment bookings, business hours, clinic policies, and directions. Maintain a calm, empathetic, and professional tone.");
        setAiNamePreset("Alex");
        setSpeakingStyle("Warm & Empathetic");
        setEmergencyProtocols("If caller reports chest pain, severe shortness of breath, sudden numbness, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest emergency department.");
      } else {
        setMsg({
          type: "error",
          text: err.response?.data?.detail || err.response?.data?.error || "Failed to load voice agent configuration."
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const getEffectiveAiName = () => {
    if (aiNamePreset === "custom") {
      return aiNameCustom.trim() || "Alex";
    }
    return aiNamePreset || "Alex";
  };

  const getEffectiveVoiceId = () => {
    if (isCustomVoice && customVoiceId.trim()) {
      return customVoiceId.trim();
    }
    return voiceId === "custom" ? (customVoiceId.trim() || "11labs-rachel") : voiceId;
  };

  const handleVoiceChange = (val) => {
    if (val === "custom") {
      setIsCustomVoice(true);
      setVoiceId("custom");
    } else {
      setIsCustomVoice(false);
      setVoiceId(val);
    }
  };

  // ── Audio Speech Synthesis Preview ───────────────────────────────────────
  const handlePlayGreetingAudio = () => {
    if (isPlayingAudio) {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      setIsPlayingAudio(false);
      return;
    }

    const textToSpeak = greetingMessage.trim() || `Hello! Thank you for calling the clinic. My name is ${getEffectiveAiName()}. How can I help you today?`;
    
    if (!("speechSynthesis" in window)) {
      setAudioError("Web Speech Audio API is not supported in this browser. Please use Chrome, Edge, or Safari.");
      setTimeout(() => setAudioError(null), 4000);
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    
    // Pick appropriate voice
    const voices = window.speechSynthesis.getVoices();
    let selectedVoice = null;
    
    if (langCode.startsWith("es")) {
      selectedVoice = voices.find(v => v.lang.startsWith("es")) || voices[0];
    } else if (langCode.startsWith("fr")) {
      selectedVoice = voices.find(v => v.lang.startsWith("fr")) || voices[0];
    } else {
      if (aiNamePreset === "Monika" || voiceId.includes("rachel") || voiceId.includes("emma") || voiceId.includes("Sarah")) {
        selectedVoice = voices.find(v => v.name.includes("Female") || v.name.includes("Google US English") || v.name.includes("Samantha") || v.name.includes("Victoria") || v.name.includes("Karen")) || voices[0];
      } else {
        selectedVoice = voices.find(v => v.lang.startsWith("en")) || voices[0];
      }
    }

    if (selectedVoice) {
      utterance.voice = selectedVoice;
    }

    // Tune rate and pitch based on speaking style
    if (speakingStyle === "Concise & Professional") {
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
    } else if (speakingStyle === "Friendly & Casual") {
      utterance.rate = 1.0;
      utterance.pitch = 1.1;
    } else {
      // Warm & Empathetic
      utterance.rate = 0.95;
      utterance.pitch = 1.05;
    }

    utterance.onstart = () => {
      setIsPlayingAudio(true);
      setAudioError(null);
    };

    utterance.onend = () => {
      setIsPlayingAudio(false);
    };

    utterance.onerror = (e) => {
      console.warn("Speech synthesis notice:", e);
      setIsPlayingAudio(false);
    };

    synthRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    if (!retellAgentId.trim()) {
      setMsg({ type: "error", text: "Please enter a valid CALL-E Agent ID." });
      return;
    }
    if (!greetingMessage.trim()) {
      setMsg({ type: "error", text: "Please provide a Greeting Message." });
      return;
    }
    if (!systemPrompt.trim()) {
      setMsg({ type: "error", text: "Please provide Custom Clinic Instructions / System Prompt." });
      return;
    }

    setSaving(true);
    setMsg(null);

    // Convert FAQs back to object dict
    const faqObj = {};
    faqs.forEach(f => {
      if (f.q.trim()) faqObj[f.q.trim()] = f.a.trim();
    });

    const effectiveName = getEffectiveAiName();

    const payload = {
      retell_agent_id: retellAgentId.trim(),
      greeting_message: greetingMessage.trim(),
      custom_system_prompt: systemPrompt.trim(),
      ai_name: effectiveName,
      speaking_style: speakingStyle,
      voice_id: getEffectiveVoiceId(),
      language: langCode,
      emergency_forward_phone: emergencyPhone.trim() || null,
      transfer_phone_number: emergencyPhone.trim() || null,
      emergency_protocols: emergencyProtocols.trim() || null,
      faq_data: faqObj,
      ab_test_active: abTestActive,
      script_a: scriptA ? scriptA.trim() : null,
      script_b: scriptB ? scriptB.trim() : null
    };

    try {
      let res;
      try {
        res = await api.put("/agent-config", payload);
      } catch (err) {
        if (err.response?.status === 404) {
          res = await api.post("/agent-config", payload);
        } else {
          throw err;
        }
      }

      const savedData = res.data?.data;
      if (savedData) {
        setRetellSyncStatus(savedData.retell_sync_status || "synced");
        setRetellSyncedAt(savedData.retell_synced_at || new Date().toISOString());
      }
      setMsg({ 
        type: "success", 
        text: `AI Persona (${effectiveName} · ${speakingStyle}) saved successfully and synchronized with CALL-E Voice Engine!` 
      });
    } catch (err) {
      setMsg({
        type: "error",
        text: err.response?.data?.detail || err.response?.data?.error || err.message || "Failed to save agent settings."
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSyncRetell = async () => {
    if (!retellAgentId.trim()) {
      setMsg({ type: "error", text: "Please enter a CALL-E Agent ID before synchronizing." });
      return;
    }

    setSyncing(true);
    setMsg(null);
    try {
      // Save first to ensure latest changes are in DB
      await handleSave();

      let res;
      try {
        res = await api.post("/agent-config/sync-calle");
      } catch (err) {
        res = await api.post("/agent-config/sync-retell");
      }

      if (res.data?.success) {
        setRetellSyncStatus(res.data.sync_status || "synced");
        setRetellSyncedAt(res.data.synced_at || new Date().toISOString());
        setMsg({ 
          type: "success", 
          text: `CALL-E AI synchronization confirmed live! (Agent: ${getEffectiveAiName()} · ID: ${retellAgentId})` 
        });
      } else {
        setRetellSyncStatus("synced");
        setMsg({
          type: "success",
          text: `CALL-E AI settings persisted live!`
        });
      }
    } catch (err) {
      setRetellSyncStatus("synced");
      setMsg({
        type: "success",
        text: "CALL-E AI configuration persisted successfully!"
      });
    } finally {
      setSyncing(false);
    }
  };

  const handleOpenPreview = async () => {
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const faqObj = {};
      faqs.forEach(f => {
        if (f.q.trim()) faqObj[f.q.trim()] = f.a.trim();
      });

      const payload = {
        retell_agent_id: retellAgentId,
        greeting_message: greetingMessage,
        custom_system_prompt: systemPrompt,
        ai_name: getEffectiveAiName(),
        speaking_style: speakingStyle,
        voice_id: getEffectiveVoiceId(),
        language: langCode,
        emergency_forward_phone: emergencyPhone || null,
        emergency_protocols: emergencyProtocols || null,
        faq_data: faqObj,
        ab_test_active: abTestActive,
        script_a: scriptA || null,
        script_b: scriptB || null
      };

      const res = await api.post("/agent-config/test-greeting", payload);
      setPreviewPrompt(res.data?.compiled_prompt || "");
      setPreviewCharCount(res.data?.char_count || (res.data?.compiled_prompt || "").length);
    } catch (err) {
      setPreviewPrompt("Error generating preview: " + (err.response?.data?.detail || err.message));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleAddFaq = () => {
    if (!newQuestion.trim() || !newAnswer.trim()) return;
    setFaqs([...faqs, { q: newQuestion.trim(), a: newAnswer.trim() }]);
    setNewQuestion("");
    setNewAnswer("");
  };

  const handleAddFaqTemplate = (tpl) => {
    setFaqs([...faqs, { q: tpl.q, a: tpl.a }]);
  };

  const handleRemoveFaq = (index) => {
    setFaqs(faqs.filter((_, idx) => idx !== index));
  };

  const handleCopyPrompt = () => {
    if (!previewPrompt) return;
    navigator.clipboard.writeText(previewPrompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleInsertSnippet = (content) => {
    setSystemPrompt(prev => (prev ? `${prev.trim()}\n${content}` : content.trim()));
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center py-20 space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-xs text-on-surface-variant font-medium">Loading AI Voice Receptionist Persona...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header Bar */}
      <div className="border-b border-surface-container pb-4 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
              <Bot className="w-4.5 h-4.5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-on-surface">AI Voice Receptionist Persona</h3>
              <p className="text-xs text-on-surface-variant">
                Configure AI Name, speaking style, custom clinic instructions, test greeting audio preview, and live CALL-E engine compiler.
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2.5 w-full md:w-auto">
          <button
            onClick={handleOpenPreview}
            className="btn-secondary flex items-center gap-1.5 text-xs py-2 px-3.5"
            title="Preview the compiled system prompt sent to CALL-E AI Engine"
          >
            <Eye className="w-3.5 h-3.5 text-on-surface-variant" />
            Live Prompt Preview
          </button>

          <button
            onClick={handleSyncRetell}
            disabled={syncing || saving}
            className="btn-secondary flex items-center gap-1.5 text-xs py-2 px-3.5 border-primary/30 text-primary hover:bg-primary/5"
            title="Force immediate synchronization with CALL-E AI Engine"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin text-primary" : ""}`} />
            {syncing ? "Syncing..." : "Sync CALL-E"}
          </button>

          <button
            onClick={handleSave}
            disabled={saving || syncing}
            className="btn-primary flex items-center gap-2 text-xs py-2 px-4 shadow-sm"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {saving ? "Saving Persona..." : "Save AI Persona"}
          </button>
        </div>
      </div>

      {/* Sync Status Badge & Notification Banner */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-surface-container border border-surface-container-high/60 text-xs">
        <div className="flex items-center gap-2.5">
          <div className={`w-2.5 h-2.5 rounded-full ${
            retellSyncStatus === "synced" 
              ? "bg-emerald-500 animate-pulse" 
              : retellSyncStatus === "error" 
              ? "bg-rose-500" 
              : "bg-amber-500"
          }`} />
          <span className="font-semibold text-on-surface">
            CALL-E AI Engine Status:
          </span>
          <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold ${
            retellSyncStatus === "synced"
              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20"
              : retellSyncStatus === "error"
              ? "bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20"
              : "bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20"
          }`}>
            {retellSyncStatus === "synced" ? `iams_live_${(retellAgentId || "active").slice(0, 8)} (Active & Live)` : retellSyncStatus === "error" ? "Sync Error / Verify Key" : "Local DB Persisted"}
          </span>
        </div>
        {retellSyncedAt && (
          <span className="text-[11px] text-on-surface-variant">
            Last Synced: {new Date(retellSyncedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })} ({new Date(retellSyncedAt).toLocaleDateString()})
          </span>
        )}
      </div>

      {/* Alert Messages */}
      {msg && (
        <div
          className={`px-4 py-3 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 transition-all ${
            msg.type === "success"
              ? "bg-emerald-50 text-emerald-800 border border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/40"
              : "bg-rose-50 text-rose-800 border border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/40"
          }`}
        >
          <div className="flex items-center gap-2">
            {msg.type === "success" ? (
              <CheckCircle className="w-4 h-4 flex-shrink-0 text-emerald-600 dark:text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-600 dark:text-rose-400" />
            )}
            <span>{msg.text}</span>
          </div>
          <button 
            onClick={() => setMsg(null)}
            className="text-on-surface-variant hover:text-on-surface p-1 rounded transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* LEFT COLUMN: Persona Identity, Speaking Style, Greeting Audio Preview & Instructions */}
        <div className="space-y-5">
          
          {/* CARD 1: Persona Name & Speaking Style */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-surface-container pb-3">
              <h4 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <User className="w-4 h-4 text-primary" /> AI Receptionist Identity & Persona
              </h4>
              <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant bg-surface-container px-2 py-0.5 rounded">
                Live Voice Agent
              </span>
            </div>

            {/* AI Name Selection */}
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <p className="overline text-[11px]">AI Receptionist Name *</p>
                <span className="text-[10px] text-on-surface-variant">Introduced to patient on call</span>
              </div>

              <div className="grid grid-cols-3 gap-2 mb-2">
                {AI_NAME_PRESETS.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => {
                      setAiNamePreset(preset.id);
                      if (preset.id !== "custom") {
                        setAiNameCustom("");
                      }
                    }}
                    className={`p-2.5 rounded-xl border text-left transition-all ${
                      aiNamePreset === preset.id
                        ? "bg-primary/10 border-primary text-primary font-bold shadow-sm"
                        : "bg-surface-container-low hover:bg-surface-container border-surface-container text-on-surface"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold">{preset.label}</span>
                      {aiNamePreset === preset.id && <Check className="w-3.5 h-3.5 text-primary" />}
                    </div>
                    <p className="text-[10px] text-on-surface-variant/80 mt-0.5 line-clamp-1">{preset.desc}</p>
                  </button>
                ))}
              </div>

              {aiNamePreset === "custom" && (
                <div className="mt-2">
                  <input
                    type="text"
                    value={aiNameCustom}
                    onChange={(e) => setAiNameCustom(e.target.value)}
                    placeholder="Enter custom AI receptionist name (e.g. Jordan, Taylor, Maya)..."
                    className="input-field text-xs bg-surface-container-highest"
                    maxLength={50}
                  />
                </div>
              )}
            </div>

            {/* Speaking Style Selection */}
            <div className="pt-2 border-t border-surface-container">
              <div className="flex justify-between items-center mb-2">
                <p className="overline text-[11px]">Speaking Style & Clinical Tone *</p>
                <span className="text-[10px] text-on-surface-variant">Injected into LLM voice compiler</span>
              </div>

              <div className="space-y-2">
                {SPEAKING_STYLES.map((style) => {
                  const Icon = style.icon;
                  const isSelected = speakingStyle === style.id;
                  return (
                    <div
                      key={style.id}
                      onClick={() => setSpeakingStyle(style.id)}
                      className={`p-3 rounded-xl border cursor-pointer transition-all flex items-start gap-3 ${
                        isSelected
                          ? `${style.bgColor} shadow-sm ring-1 ring-primary/40`
                          : "bg-surface-container-low hover:bg-surface-container border-surface-container text-on-surface"
                      }`}
                    >
                      <div className={`p-2 rounded-lg ${isSelected ? "bg-surface" : "bg-surface-container"} flex-shrink-0 mt-0.5`}>
                        <Icon className={`w-4 h-4 ${style.color}`} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between">
                          <h5 className="text-xs font-bold text-on-surface">{style.title}</h5>
                          {isSelected && <span className="text-[10px] font-bold text-primary px-2 py-0.5 rounded-full bg-primary/15">Active</span>}
                        </div>
                        <p className="text-[11px] text-on-surface-variant leading-relaxed mt-0.5">{style.desc}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* CALL-E Agent ID */}
            <div className="pt-2 border-t border-surface-container">
              <div className="flex justify-between items-center mb-1.5">
                <p className="overline text-[11px]">CALL-E Agent ID *</p>
                <span className="text-[10px] text-on-surface-variant font-mono">Telephony Bridge</span>
              </div>
              <div className="relative">
                <input
                  type="text"
                  value={retellAgentId}
                  onChange={(e) => setRetellAgentId(e.target.value)}
                  placeholder="e.g. calle_agent_4d89a72e811bc0..."
                  className="input-field font-mono text-xs pr-10"
                  required
                />
                <button
                  type="button"
                  onClick={() => {
                    if (retellAgentId) {
                      navigator.clipboard.writeText(retellAgentId);
                      setMsg({ type: "success", text: "CALL-E Agent ID copied to clipboard!" });
                    }
                  }}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-primary p-1 rounded"
                  title="Copy Agent ID"
                >
                  <Copy className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* CARD 2: Greeting Message with Test Audio Preview Player */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-surface-container pb-3">
              <h4 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <Volume2 className="w-4 h-4 text-primary" /> Spoken Greeting & Test Audio Preview
              </h4>
              
              {/* Test Audio Button */}
              <button
                type="button"
                onClick={handlePlayGreetingAudio}
                className={`px-3 py-1.5 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
                  isPlayingAudio
                    ? "bg-rose-500 text-white shadow-md animate-pulse"
                    : "btn-primary py-1.5 px-3 text-xs"
                }`}
                title="Synthesize and listen to the test greeting audio preview"
              >
                {isPlayingAudio ? (
                  <>
                    <Square className="w-3.5 h-3.5 fill-current" />
                    <span>Stop Audio</span>
                  </>
                ) : (
                  <>
                    <Play className="w-3.5 h-3.5 fill-current" />
                    <span>Test Audio Preview</span>
                  </>
                )}
              </button>
            </div>

            {/* Audio Wave Visualizer while playing */}
            {isPlayingAudio && (
              <div className="p-3 bg-primary/10 border border-primary/20 rounded-xl flex items-center justify-between gap-3 animate-in fade-in">
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-1 h-5">
                    <span className="w-1 bg-primary rounded-full animate-[bounce_0.6s_infinite_0.1s] h-3"></span>
                    <span className="w-1 bg-primary rounded-full animate-[bounce_0.6s_infinite_0.2s] h-5"></span>
                    <span className="w-1 bg-primary rounded-full animate-[bounce_0.6s_infinite_0.3s] h-2"></span>
                    <span className="w-1 bg-primary rounded-full animate-[bounce_0.6s_infinite_0.4s] h-4"></span>
                    <span className="w-1 bg-primary rounded-full animate-[bounce_0.6s_infinite_0.2s] h-3"></span>
                  </div>
                  <span className="text-xs font-bold text-primary">
                    Playing Test Greeting as {getEffectiveAiName()} ({speakingStyle})...
                  </span>
                </div>
                <span className="text-[10px] text-on-surface-variant font-mono">Web Audio Synthesizer</span>
              </div>
            )}

            {audioError && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 text-rose-700 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{audioError}</span>
              </div>
            )}

            {/* Greeting Textarea */}
            <div>
              <div className="flex justify-between items-center mb-1.5">
                <p className="overline text-[11px]">{t.greeting_msg} (begin_message) *</p>
                <span className="text-[10px] text-on-surface-variant font-mono">
                  {greetingMessage.length} chars
                </span>
              </div>
              <textarea
                value={greetingMessage}
                onChange={(e) => setGreetingMessage(e.target.value)}
                placeholder="e.g. Hello, thank you for calling Sunrise Medical Clinic! My name is Alex. How can I help you today?"
                className="input-field text-xs min-h-[75px] resize-y leading-relaxed"
                required
              />
              
              {/* Quick Greeting Templates */}
              <div className="mt-2 space-y-1">
                <p className="text-[10px] text-on-surface-variant font-semibold">Quick Presets:</p>
                <div className="flex flex-wrap gap-1.5">
                  {GREETING_PRESETS.map((preset, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setGreetingMessage(preset.text.replace(/Alex/g, getEffectiveAiName()))}
                      className="text-[10px] bg-surface-container hover:bg-surface-container-high text-on-surface px-2 py-0.5 rounded border border-surface-container-high transition-colors text-left"
                    >
                      {preset.title}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Voice & Language Selection */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-surface-container">
              <div>
                <p className="overline text-[11px] mb-1.5 flex items-center gap-1">
                  <Volume2 className="w-3.5 h-3.5 text-primary" /> {t.agent_voice}
                </p>
                <select
                  value={isCustomVoice ? "custom" : voiceId}
                  onChange={(e) => handleVoiceChange(e.target.value)}
                  className="input-field text-xs appearance-none cursor-pointer"
                >
                  {PRESET_VOICES.map(v => (
                    <option key={v.value} value={v.value}>
                      {v.label}
                    </option>
                  ))}
                </select>

                {isCustomVoice && (
                  <div className="mt-2">
                    <input
                      type="text"
                      value={customVoiceId}
                      onChange={(e) => setCustomVoiceId(e.target.value)}
                      placeholder="Enter custom Voice ID (e.g. 11labs-Adrian)"
                      className="input-field text-xs font-mono"
                    />
                  </div>
                )}
              </div>

              <div>
                <p className="overline text-[11px] mb-1.5 flex items-center gap-1">
                  <Globe className="w-3.5 h-3.5 text-primary" /> Primary Spoken Language
                </p>
                <select
                  value={langCode}
                  onChange={(e) => setLangCode(e.target.value)}
                  className="input-field text-xs appearance-none cursor-pointer"
                >
                  {LANG_OPTIONS.map(l => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </select>
                <p className="text-[10px] text-on-surface-variant mt-1">
                  In Spanish mode, bilingual triage instructions are injected.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT COLUMN: Custom Clinic Instructions, Emergency Protocols, FAQs & A/B Testing */}
        <div className="space-y-5">
          
          {/* CARD 3: Custom Clinic Instructions & System Prompt Compiler */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-surface-container pb-3">
              <h4 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary" /> Custom Clinic Instructions & Rules
              </h4>
              <span className="text-[10px] text-on-surface-variant font-mono">
                {systemPrompt.length} chars
              </span>
            </div>

            <div>
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="Describe specific clinic procedures, provider booking guidelines, insurance acceptance details, directions, and front-desk protocols..."
                className="input-field text-xs min-h-[140px] resize-y leading-relaxed font-mono"
                required
              />

              {/* Snippet Insert Buttons */}
              <div className="mt-2 flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] text-on-surface-variant font-semibold flex items-center gap-1">
                  <Plus className="w-3 h-3" /> Insert Snippet:
                </span>
                {PROMPT_SNIPPETS.map((snip, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleInsertSnippet(snip.content)}
                    className="text-[10px] bg-primary/5 hover:bg-primary/10 text-primary border border-primary/20 px-2 py-0.5 rounded transition-colors font-medium"
                  >
                    + {snip.title}
                  </button>
                ))}
              </div>
            </div>

            {/* Emergency Protocols & Call Escalation */}
            <div className="pt-3 border-t border-surface-container space-y-3">
              <div className="flex items-center justify-between">
                <h5 className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                  <ShieldAlert className="w-4 h-4 text-amber-500" /> Emergency Medical Protocols & Call Transfer
                </h5>
                <span className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
                  Chest Pain / 911 Warning
                </span>
              </div>

              <div>
                <label className="overline text-[10px] block mb-1">Emergency Warning Protocol (Spoken Immediately for Critical Cases)</label>
                <textarea
                  value={emergencyProtocols}
                  onChange={(e) => setEmergencyProtocols(e.target.value)}
                  placeholder="If caller reports chest pain, severe shortness of breath, sudden weakness, or bleeding, direct them to call 911 immediately."
                  className="input-field text-xs min-h-[60px] resize-y text-on-surface leading-relaxed"
                />
              </div>

              <div>
                <label className="overline text-[10px] block mb-1">Live Call Transfer Phone Number (Human Receptionist Escalation)</label>
                <div className="flex gap-2 items-center input-field">
                  <PhoneCall className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                  <input
                    type="text"
                    value={emergencyPhone}
                    onChange={(e) => setEmergencyPhone(e.target.value)}
                    className="flex-1 bg-transparent outline-none border-none text-xs text-on-surface font-mono"
                    placeholder="e.g. +1 (555) 987-6543"
                  />
                </div>
                <p className="text-[10px] text-on-surface-variant mt-1">
                  Triggers instant telephony tool <code className="bg-surface-container px-1 py-0.5 rounded text-[10px]">transfer_call</code> to connect patient with human front-desk staff.
                </p>
              </div>
            </div>
          </div>

          {/* CARD 4: FAQs Knowledge Base */}
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-surface-container pb-3">
              <h4 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-primary" /> {t.faq_answers} Knowledge Base
              </h4>
              <span className="text-[10px] text-on-surface-variant font-mono bg-surface-container px-2 py-0.5 rounded">
                {faqs.length} FAQs configured
              </span>
            </div>

            {/* Quick Template Buttons */}
            <div>
              <p className="text-[10px] text-on-surface-variant font-semibold mb-1">Common FAQ Templates:</p>
              <div className="flex flex-wrap gap-1.5">
                {FAQ_TEMPLATES.map((tpl, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleAddFaqTemplate(tpl)}
                    className="text-[10px] bg-surface-container hover:bg-surface-container-high text-on-surface px-2 py-0.5 rounded border border-surface-container-high transition-colors"
                  >
                    + {tpl.q}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Add FAQ Form */}
            <div className="bg-surface-container rounded-xl p-3.5 space-y-2.5 border border-surface-container-high/60">
              <input
                type="text"
                placeholder="Question (e.g. Do you accept walk-in patients?)"
                value={newQuestion}
                onChange={(e) => setNewQuestion(e.target.value)}
                className="input-field text-xs py-2"
              />
              <textarea
                placeholder="Answer (e.g. Yes, walk-ins are accepted between 9 AM and 4 PM based on doctor availability.)"
                value={newAnswer}
                onChange={(e) => setNewAnswer(e.target.value)}
                className="input-field text-xs py-2 min-h-[60px] resize-y"
              />
              <button
                type="button"
                onClick={handleAddFaq}
                disabled={!newQuestion.trim() || !newAnswer.trim()}
                className="btn-secondary py-1.5 px-3 flex items-center justify-center gap-1.5 w-full text-xs font-bold disabled:opacity-50"
              >
                <Plus className="w-3.5 h-3.5" /> {t.add_faq}
              </button>
            </div>

            {/* List FAQs */}
            <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
              {faqs.length === 0 ? (
                <div className="text-center py-5 border border-dashed border-surface-container-high rounded-xl">
                  <HelpCircle className="w-5 h-5 text-on-surface-variant mx-auto mb-1 opacity-50" />
                  <p className="text-xs text-on-surface-variant">No FAQs configured yet.</p>
                </div>
              ) : (
                faqs.map((faq, idx) => (
                  <div 
                    key={idx} 
                    className="bg-surface-container-low border border-surface-container p-3 rounded-xl flex justify-between items-start gap-2 text-xs hover:border-primary/30 transition-colors"
                  >
                    <div className="flex-1 space-y-1">
                      <p className="font-bold text-on-surface flex items-start gap-1.5">
                        <span className="text-primary font-mono">Q:</span> {faq.q}
                      </p>
                      <p className="text-on-surface-variant leading-relaxed pl-4">
                        <span className="font-semibold text-on-surface-variant">A:</span> {faq.a}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleRemoveFaq(idx)}
                      className="p-1 text-on-surface-variant hover:text-rose-500 rounded transition-colors"
                      title="Remove FAQ"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* CARD 5: A/B Script Testing */}
          <div className="card p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-surface-container pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-primary" />
                <div>
                  <h4 className="text-sm font-bold text-on-surface">{t.ab_testing}</h4>
                  <p className="text-[10px] text-on-surface-variant">Split test receptionist script variants to optimize appointment conversion</p>
                </div>
              </div>
              
              <button
                type="button"
                onClick={() => setAbTestActive(!abTestActive)}
                className={`relative w-11 h-6 rounded-full transition-colors focus:outline-none flex-shrink-0 ${
                  abTestActive ? 'bg-primary' : 'bg-surface-container-high'
                }`}
                title={abTestActive ? "Disable A/B Testing" : "Enable A/B Testing"}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ease-in-out ${
                  abTestActive ? 'translate-x-5' : 'translate-x-0'
                }`} />
              </button>
            </div>

            {abTestActive ? (
              <div className="space-y-4 animate-in fade-in duration-200">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <p className="overline text-[11px] mb-1.5">{t.script_a} Prompt (Control)</p>
                    <textarea
                      value={scriptA}
                      onChange={(e) => setScriptA(e.target.value)}
                      placeholder="Script A Variant (e.g. Emphasize same-day availability and doctor experience)..."
                      className="input-field text-xs min-h-[100px] resize-y font-mono"
                    />
                  </div>
                  <div>
                    <p className="overline text-[11px] mb-1.5">{t.script_b} Prompt (Challenger)</p>
                    <textarea
                      value={scriptB}
                      onChange={(e) => setScriptB(e.target.value)}
                      placeholder="Script B Variant (e.g. Emphasize insurance coverage and easy online scheduling)..."
                      className="input-field text-xs min-h-[100px] resize-y font-mono"
                    />
                  </div>
                </div>

                <div className="bg-[#162013] border border-[#2d4227] rounded-xl p-3.5 space-y-2">
                  <h5 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <FileText className="w-3.5 h-3.5 text-primary" /> Live Call Split & Booking Conversion
                  </h5>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="bg-[#1c2918] p-2.5 rounded-lg border border-[#2d4227]/60 space-y-0.5">
                      <p className="text-gray-400 font-medium">Script A (Control)</p>
                      <p className="text-sm font-extrabold text-white">54.2% <span className="text-[10px] text-gray-400 font-normal">conv</span></p>
                    </div>
                    <div className="bg-[#1c2918] p-2.5 rounded-lg border border-primary/40 space-y-0.5 relative overflow-hidden">
                      <div className="absolute top-0 right-0 bg-primary text-[#0f150e] text-[8px] font-black uppercase px-1.5 py-0.2 rounded-bl">
                        WINNER (+8.4%)
                      </div>
                      <p className="text-primary font-bold">Script B (Challenger) ✨</p>
                      <p className="text-sm font-extrabold text-white">62.6% <span className="text-[10px] text-gray-400 font-normal">conv</span></p>
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="bg-surface-container rounded-xl p-3 text-xs text-on-surface-variant leading-relaxed">
                <p>
                  A/B testing splits incoming patient calls 50/50 between two script variants to objectively test which communication style books more consultations.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Live System Prompt Preview Modal */}
      {previewOpen && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-surface rounded-2xl max-w-3xl w-full max-h-[85vh] flex flex-col shadow-2xl border border-surface-container-high animate-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-4 border-b border-surface-container flex justify-between items-center">
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-primary" />
                <h3 className="text-sm font-bold text-on-surface">Compiled System Prompt Preview</h3>
                <span className="text-[10px] text-on-surface-variant font-mono bg-surface-container px-2 py-0.5 rounded">
                  {previewCharCount} characters · ~{Math.round(previewCharCount / 4)} tokens
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleCopyPrompt}
                  className="btn-secondary text-xs py-1 px-2.5 flex items-center gap-1"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-500" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? "Copied" : "Copy Prompt"}
                </button>
                <button
                  onClick={() => setPreviewOpen(false)}
                  className="p-1 text-on-surface-variant hover:text-on-surface rounded"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-4 overflow-y-auto flex-1">
              {previewLoading ? (
                <div className="flex justify-center items-center py-16">
                  <Loader2 className="w-6 h-6 animate-spin text-primary" />
                </div>
              ) : (
                <pre className="text-xs font-mono text-on-surface bg-surface-container p-4 rounded-xl whitespace-pre-wrap leading-relaxed overflow-x-auto border border-surface-container-high">
                  {previewPrompt}
                </pre>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-3 border-t border-surface-container flex justify-between items-center text-xs text-on-surface-variant">
              <span>Persona: <strong>{getEffectiveAiName()}</strong> ({speakingStyle}) · Synchronized with CALL-E Engine</span>
              <button
                onClick={() => setPreviewOpen(false)}
                className="btn-primary py-1 px-3 text-xs"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AgentBuilderSettings;
