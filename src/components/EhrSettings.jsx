import React, { useState, useEffect, useMemo } from "react";
import {
  Loader2,
  CheckCircle2,
  AlertCircle,
  Wifi,
  RefreshCw,
  Trash2,
  Settings,
  ExternalLink,
  Activity,
  Search,
  Database,
  Sliders,
  Eye,
  EyeOff,
  Server,
  Check,
  X,
  Clock,
  PlayCircle,
  Zap,
  HelpCircle,
} from "lucide-react";
import api from "../lib/api";

const PROVIDER_DEFINITIONS = [
  {
    id: "drchrono",
    name: "DrChrono EHR",
    category: "Ambulatory & Specialty",
    badge: "REST API v4",
    description: "Full bidirectional sync for patient demographics, appointments, clinical notes, and physician scheduling.",
    docsUrl: "https://drchrono.com/api-docs/",
    defaultEndpoint: "https://drchrono.com/api",
    fields: [
      { key: "fhir_endpoint", label: "API Base URL", type: "text", placeholder: "https://drchrono.com/api", defaultVal: "https://drchrono.com/api" },
      { key: "provider_clinic_id", label: "Doctor / Provider ID", type: "text", placeholder: "e.g. 294810 (Optional)", hint: "DrChrono Doctor ID for appointment assignments" },
      { key: "client_id", label: "OAuth Client ID", type: "text", placeholder: "DrChrono App Client ID" },
      { key: "client_secret", label: "OAuth Client Secret", type: "password", placeholder: "Client Secret" },
      { key: "access_token", label: "OAuth Access Token", type: "password", placeholder: "Bearer token from DrChrono OAuth2" },
      { key: "refresh_token", label: "Refresh Token", type: "password", placeholder: "Optional refresh token" },
    ],
  },
  {
    id: "athenahealth",
    name: "AthenaHealth (AthenaOne)",
    category: "Enterprise Practice",
    badge: "AthenaNet / Preview",
    description: "Enterprise patient registration, demographics, insurance eligibility, and multi-department scheduling bridge.",
    docsUrl: "https://developer.athenahealth.com/",
    defaultEndpoint: "https://api.preview.platform.athenahealth.com/v1",
    fields: [
      { key: "fhir_endpoint", label: "API Base URL", type: "text", placeholder: "https://api.preview.platform.athenahealth.com/v1", defaultVal: "https://api.preview.platform.athenahealth.com/v1" },
      { key: "provider_clinic_id", label: "Practice ID (Context)", type: "text", placeholder: "e.g. 195900", defaultVal: "195900", hint: "AthenaNet Practice ID (195900 is standard preview sandbox)" },
      { key: "client_id", label: "Athena Client ID (API Key)", type: "text", placeholder: "Your Athena API Key" },
      { key: "client_secret", label: "Client Secret", type: "password", placeholder: "Your Athena Client Secret" },
      { key: "access_token", label: "Access Token / Bearer Key", type: "password", placeholder: "Bearer token" },
    ],
  },
  {
    id: "epic",
    name: "Epic Systems (FHIR R4)",
    category: "Hospital & Health Systems",
    badge: "SMART on FHIR R4",
    description: "Hospital EHR integration bridge with Epic Interconnect. Synchronizes Patient demographics and Appointment bookings.",
    docsUrl: "https://open.epic.com/Interface/FHIR",
    defaultEndpoint: "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
    fields: [
      { key: "fhir_endpoint", label: "Epic FHIR R4 Endpoint", type: "text", placeholder: "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4", defaultVal: "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4" },
      { key: "access_token", label: "SMART Bearer Token", type: "password", placeholder: "OAuth2 Bearer Token from Epic Interconnect" },
      { key: "client_id", label: "Epic App Client ID", type: "text", placeholder: "Non-production or production Client ID" },
      { key: "client_secret", label: "Client Secret (Optional)", type: "password", placeholder: "Client secret if confidential client" },
    ],
  },
  {
    id: "cerner",
    name: "Cerner / Oracle Health",
    category: "Hospital & Health Systems",
    badge: "SMART on FHIR R4",
    description: "Oracle Health / Cerner Millennium clinical workflow connector. Supports standard FHIR R4 Patient & Appointment resources.",
    docsUrl: "https://fhir.cerner.com/",
    defaultEndpoint: "https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d",
    fields: [
      { key: "fhir_endpoint", label: "Cerner FHIR R4 Endpoint", type: "text", placeholder: "https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d", defaultVal: "https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d" },
      { key: "access_token", label: "Cerner Bearer Token", type: "password", placeholder: "OAuth2 Bearer Token from Cerner Code Console" },
      { key: "client_id", label: "Cerner System Client ID", type: "text", placeholder: "App Client ID" },
      { key: "client_secret", label: "Client Secret", type: "password", placeholder: "Cerner Client Secret" },
    ],
  },
  {
    id: "fhir",
    name: "Custom SMART on FHIR R4",
    category: "Hospital & Health Systems",
    badge: "Open FHIR Server",
    description: "Connect any ONC-certified FHIR R4 repository (HAPI FHIR, NextGen, Allscripts, eClinicalWorks, MEDITECH).",
    docsUrl: "https://hl7.org/fhir/R4/",
    defaultEndpoint: "https://hapi.fhir.org/baseR4",
    fields: [
      { key: "fhir_endpoint", label: "FHIR R4 Server Base URL", type: "text", placeholder: "https://hapi.fhir.org/baseR4", defaultVal: "https://hapi.fhir.org/baseR4" },
      { key: "access_token", label: "Bearer Token (Optional)", type: "password", placeholder: "Auth token (leave empty if open public server)" },
      { key: "client_id", label: "Client ID (Optional)", type: "text", placeholder: "OAuth Client ID" },
      { key: "client_secret", label: "Client Secret (Optional)", type: "password", placeholder: "OAuth Client Secret" },
    ],
  },
  {
    id: "jane",
    name: "Jane App",
    category: "Mental & Allied Health",
    badge: "REST API v2",
    description: "Integrated clinic management and booking for Canadian and US allied health practices and physical therapy.",
    docsUrl: "https://jane.app/guide",
    defaultEndpoint: "https://jane.app/api/v2",
    fields: [
      { key: "provider_clinic_id", label: "Jane Clinic Subdomain", type: "text", placeholder: "e.g. clinicname (without .janeapp.com)", hint: "Subdomain used to access your Jane account" },
      { key: "access_token", label: "Jane API Bearer Token", type: "password", placeholder: "Paste Jane App API Key / OAuth Token" },
    ],
  },
  {
    id: "simplepractice",
    name: "SimplePractice",
    category: "Mental & Allied Health",
    badge: "REST API v1",
    description: "Practice management system for mental health practitioners, social workers, psychologists, and therapists.",
    docsUrl: "https://api.simplepractice.com/",
    defaultEndpoint: "https://api.simplepractice.com/api/v1",
    fields: [
      { key: "access_token", label: "SimplePractice Access Token", type: "password", placeholder: "Paste SimplePractice API token" },
    ],
  },
  {
    id: "zapier",
    name: "Zapier Webhook Bridge",
    category: "Automation & Webhooks",
    badge: "Webhook Stream",
    description: "Real-time webhook events for patient creations and appointment schedules dispatching to 5,000+ connected SaaS apps.",
    docsUrl: "https://zapier.com/apps/webhook",
    defaultEndpoint: "",
    fields: [
      { key: "webhook_secret", label: "Zapier Catch Hook URL", type: "text", placeholder: "https://hooks.zapier.com/hooks/catch/..." },
    ],
  },
];

const SYNC_FREQUENCY_OPTIONS = [
  { value: "realtime", label: "⚡ Real-time (Instant)", desc: "Syncs immediately on each booking/patient update" },
  { value: "15m", label: "⏱️ Every 15 Minutes", desc: "Batch scheduled sync every 15 minutes" },
  { value: "1h", label: "🕐 Every Hour", desc: "Hourly batch reconciliation" },
  { value: "daily", label: "📅 Daily (Nightly)", desc: "Once per 24 hours at midnight UTC" },
  { value: "manual", label: "🖐️ Manual Only", desc: "Sync only triggered manually on demand" },
];

const CATEGORIES = ["All", "Hospital & Health Systems", "Ambulatory & Specialty", "Mental & Allied Health", "Automation & Webhooks", "Enterprise Practice"];

const EhrSettings = () => {
  const [integrations, setIntegrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [syncingProvider, setSyncingProvider] = useState(null); // providerId being tested
  const [triggeringFullSync, setTriggeringFullSync] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);
  const [activeCategory, setActiveCategory] = useState("All");
  const [searchQuery, setSearchQuery] = useState("");

  // Configuration Modal state
  const [editingProvider, setEditingProvider] = useState(null);
  const [formData, setFormData] = useState({});
  const [showPasswords, setShowPasswords] = useState({});
  const [modalSaving, setModalSaving] = useState(false);
  const [modalTesting, setModalTesting] = useState(false);
  const [modalStatus, setModalStatus] = useState(null);

  // Live FHIR Diagnostics Tool state
  const [showFhirTester, setShowFhirTester] = useState(false);
  const [fhirTestUrl, setFhirTestUrl] = useState("https://hapi.fhir.org/baseR4");
  const [fhirTestToken, setFhirTestToken] = useState("");
  const [fhirTestLoading, setFhirTestLoading] = useState(false);
  const [fhirTestResult, setFhirTestResult] = useState(null);

  useEffect(() => {
    fetchIntegrations();
  }, []);

  const fetchIntegrations = async () => {
    setLoading(true);
    try {
      const res = await api.get("/ehr/integrations");
      const data = res.data?.data || [];
      setIntegrations(data);
    } catch (e) {
      console.error("Failed to load integrations", e);
      setStatusMsg({
        type: "error",
        text: e.response?.data?.detail || "Could not load EHR integrations.",
      });
    } finally {
      setLoading(false);
    }
  };

  const openConfigModal = (providerDef) => {
    const existing = integrations.find((i) => i.provider_name === providerDef.id);
    const initialForm = {
      provider_name: providerDef.id,
      sync_frequency: existing?.sync_frequency || "realtime",
      sync_enabled: existing?.sync_enabled !== undefined ? existing.sync_enabled : true,
      fhir_endpoint: existing?.fhir_endpoint || providerDef.defaultEndpoint || "",
      provider_clinic_id: existing?.provider_clinic_id || "",
      client_id: existing?.client_id || "",
      client_secret: existing?.client_secret || "",
      access_token: existing?.access_token || "",
      refresh_token: existing?.refresh_token || "",
      webhook_secret: existing?.webhook_secret || "",
    };

    setFormData(initialForm);
    setEditingProvider(providerDef);
    setModalStatus(null);
    setShowPasswords({});
  };

  const closeConfigModal = () => {
    setEditingProvider(null);
    setFormData({});
    setModalStatus(null);
  };

  const handleSaveModal = async (e) => {
    if (e) e.preventDefault();
    if (!editingProvider) return;

    setModalSaving(true);
    setModalStatus(null);

    try {
      const payload = {
        provider_name: editingProvider.id,
        sync_frequency: formData.sync_frequency || "realtime",
        sync_enabled: Boolean(formData.sync_enabled),
        is_active: true,
        fhir_endpoint: formData.fhir_endpoint?.trim() || null,
        provider_clinic_id: formData.provider_clinic_id?.trim() || null,
        client_id: formData.client_id?.trim() || null,
        client_secret: formData.client_secret?.trim() || null,
        access_token: formData.access_token?.trim() || null,
        refresh_token: formData.refresh_token?.trim() || null,
        webhook_secret: formData.webhook_secret?.trim() || null,
      };

      const res = await api.post("/ehr/integrations", payload);
      setStatusMsg({
        type: "success",
        text: res.data?.message || `${editingProvider.name} configuration saved successfully!`,
      });
      await fetchIntegrations();
      closeConfigModal();
    } catch (err) {
      setModalStatus({
        type: "error",
        text: err.response?.data?.detail || err.response?.data?.error || err.message,
      });
    } finally {
      setModalSaving(false);
    }
  };

  const handleTestModalConnection = async () => {
    if (!editingProvider) return;
    setModalTesting(true);
    setModalStatus(null);

    try {
      const res = await api.post(`/ehr/integrations/${editingProvider.id}/verify`, {
        provider_name: editingProvider.id,
        fhir_endpoint: formData.fhir_endpoint?.trim() || null,
        provider_clinic_id: formData.provider_clinic_id?.trim() || null,
        client_id: formData.client_id?.trim() || null,
        client_secret: formData.client_secret?.trim() || null,
        access_token: formData.access_token?.trim() || null,
        refresh_token: formData.refresh_token?.trim() || null,
        webhook_secret: formData.webhook_secret?.trim() || null,
      });

      if (res.data?.data?.connected) {
        setModalStatus({
          type: "success",
          text: res.data?.data?.message || "Connection verified! EHR endpoint responded successfully.",
        });
      } else {
        setModalStatus({
          type: "error",
          text: res.data?.data?.message || "Connection test failed. Please verify credentials and URL.",
        });
      }
    } catch (err) {
      setModalStatus({
        type: "error",
        text: err.response?.data?.detail || err.response?.data?.error || err.message,
      });
    } finally {
      setModalTesting(false);
    }
  };

  const handleVerifySaved = async (providerId, providerName) => {
    setStatusMsg(null);
    setSyncingProvider(providerId);
    try {
      const res = await api.post(`/ehr/integrations/${providerId}/verify`);
      if (res.data?.data?.connected) {
        setStatusMsg({
          type: "success",
          text: `Connection verified! ${providerName} is online and operational.`,
        });
      } else {
        setStatusMsg({
          type: "error",
          text: `Connection check failed for ${providerName}. Please check API credentials.`,
        });
      }
    } catch (err) {
      setStatusMsg({
        type: "error",
        text: err.response?.data?.detail || err.response?.data?.error || err.message,
      });
    } finally {
      setSyncingProvider(null);
    }
  };

  const handleDisconnect = async (providerId, providerName) => {
    setStatusMsg(null);
    if (!window.confirm(`Are you sure you want to disconnect ${providerName}? Local mappings will be preserved, but automatic syncing will stop.`)) {
      return;
    }

    try {
      await api.delete(`/ehr/integrations/${providerId}`);
      setStatusMsg({
        type: "success",
        text: `${providerName} disconnected successfully.`,
      });
      await fetchIntegrations();
    } catch (err) {
      setStatusMsg({
        type: "error",
        text: err.response?.data?.detail || err.response?.data?.error || err.message,
      });
    }
  };

  const handlePatchToggleSync = async (providerId, currentEnabled) => {
    const nextVal = !currentEnabled;
    try {
      // Optimistic update
      setIntegrations((prev) =>
        prev.map((i) => (i.provider_name === providerId ? { ...i, sync_enabled: nextVal } : i))
      );

      await api.patch(`/ehr/integrations/${providerId}`, {
        sync_enabled: nextVal,
      });
      setStatusMsg({
        type: "success",
        text: `Sync ${nextVal ? "enabled" : "paused"} for ${providerId.toUpperCase()}.`,
      });
    } catch (err) {
      await fetchIntegrations();
      setStatusMsg({
        type: "error",
        text: err.response?.data?.detail || "Failed to update sync toggle.",
      });
    }
  };

  const handlePatchFrequency = async (providerId, newFreq) => {
    try {
      // Optimistic update
      setIntegrations((prev) =>
        prev.map((i) => (i.provider_name === providerId ? { ...i, sync_frequency: newFreq } : i))
      );

      await api.patch(`/ehr/integrations/${providerId}`, {
        sync_frequency: newFreq,
      });
      setStatusMsg({
        type: "success",
        text: `Sync frequency for ${providerId.toUpperCase()} updated to ${newFreq.toUpperCase()}.`,
      });
    } catch (err) {
      await fetchIntegrations();
      setStatusMsg({
        type: "error",
        text: err.response?.data?.detail || "Failed to update sync frequency.",
      });
    }
  };

  const handleTriggerFullSync = async () => {
    setTriggeringFullSync(true);
    setStatusMsg(null);
    try {
      const res = await api.post("/ehr/sync/run");
      const data = res.data?.data;
      if (data?.synced) {
        setStatusMsg({
          type: "success",
          text: `EHR Sync Triggered! Active providers synced: ${(data.active_providers || []).join(", ") || "All"} at ${new Date().toLocaleTimeString()}.`,
        });
      } else {
        setStatusMsg({
          type: "error",
          text: data?.message || "No active integrations to sync.",
        });
      }
      await fetchIntegrations();
    } catch (err) {
      setStatusMsg({
        type: "error",
        text: err.response?.data?.detail || "Manual EHR sync failed.",
      });
    } finally {
      setTriggeringFullSync(false);
    }
  };

  const handleRunFhirDiagnostic = async () => {
    if (!fhirTestUrl) return;
    setFhirTestLoading(true);
    setFhirTestResult(null);

    try {
      const res = await api.post("/ehr/diagnostics/fhir", {
        fhir_endpoint: fhirTestUrl.trim(),
        access_token: fhirTestToken.trim() || null,
      });
      setFhirTestResult(res.data?.data);
    } catch (err) {
      setFhirTestResult({
        online: false,
        status_code: 500,
        message: err.response?.data?.detail || err.message || "Failed to query FHIR server.",
      });
    } finally {
      setFhirTestLoading(false);
    }
  };

  const togglePasswordVisibility = (fieldKey) => {
    setShowPasswords((prev) => ({ ...prev, [fieldKey]: !prev[fieldKey] }));
  };

  // Filtered providers
  const filteredProviders = useMemo(() => {
    return PROVIDER_DEFINITIONS.filter((p) => {
      const matchCategory = activeCategory === "All" || p.category === activeCategory;
      const matchSearch =
        searchQuery.trim() === "" ||
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.id.toLowerCase().includes(searchQuery.toLowerCase());
      return matchCategory && matchSearch;
    });
  }, [activeCategory, searchQuery]);

  // Statistics
  const connectedCount = useMemo(() => {
    return integrations.filter((i) => i.is_active).length;
  }, [integrations]);

  const activeSyncCount = useMemo(() => {
    return integrations.filter((i) => i.is_active && i.sync_enabled).length;
  }, [integrations]);

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center py-20 space-y-3">
        <Loader2 className="w-9 h-9 animate-spin text-primary" />
        <p className="text-xs font-semibold text-on-surface-variant">Loading EHR Integration Modules...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header Banner & Status Bar */}
      <div className="bg-surface-container-low rounded-2xl p-6 border border-surface-container flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5 shadow-sm">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="p-2 bg-primary/10 text-primary rounded-xl">
              <Database className="w-5 h-5" />
            </span>
            <div>
              <h2 className="text-lg font-bold text-on-surface">EHR & EMR Interoperability Hub</h2>
              <p className="text-xs text-on-surface-variant">
                Bidirectional synchronization for DrChrono, AthenaHealth, Epic Systems, Cerner / Oracle Health, and SMART on FHIR R4 servers.
              </p>
            </div>
          </div>
        </div>

        {/* Global Action & Summary Stats */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-3 px-3.5 py-2 bg-surface-container rounded-xl border border-surface-container-high text-xs">
            <div>
              <span className="text-[10px] uppercase font-bold text-on-surface-variant block">Connected</span>
              <span className="font-extrabold text-on-surface text-sm">{connectedCount} / {PROVIDER_DEFINITIONS.length}</span>
            </div>
            <div className="h-6 w-px bg-outline-variant/40" />
            <div>
              <span className="text-[10px] uppercase font-bold text-on-surface-variant block">Auto-Sync</span>
              <span className="font-extrabold text-primary text-sm">{activeSyncCount} Active</span>
            </div>
          </div>

          <button
            onClick={() => setShowFhirTester(!showFhirTester)}
            className={`px-3.5 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all border ${
              showFhirTester
                ? "bg-primary text-white border-primary"
                : "bg-surface-container hover:bg-surface-container-high text-on-surface border-surface-container-high"
            }`}
          >
            <Server className="w-4 h-4" />
            <span>FHIR Sandbox</span>
          </button>

          <button
            onClick={handleTriggerFullSync}
            disabled={triggeringFullSync || connectedCount === 0}
            className="px-4 py-2 rounded-xl text-xs font-bold bg-primary hover:bg-primary/90 text-white flex items-center gap-2 transition-all disabled:opacity-50 shadow-sm"
          >
            {triggeringFullSync ? <Loader2 className="w-4 h-4 animate-spin" /> : <PlayCircle className="w-4 h-4" />}
            <span>Sync All Integrations</span>
          </button>
        </div>
      </div>

      {/* Status Alerts */}
      {statusMsg && (
        <div
          className={`px-4 py-3 rounded-xl text-sm font-semibold flex items-center justify-between gap-2 transition-all ${
            statusMsg.type === "success"
              ? "bg-[#edf7e0] text-[#396a00] border border-[#7FCD4D]/30"
              : "bg-[#fce4ec] text-[#b71c1c] border border-rose-200"
          }`}
        >
          <div className="flex items-center gap-2">
            {statusMsg.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
            )}
            <span>{statusMsg.text}</span>
          </div>
          <button onClick={() => setStatusMsg(null)} className="text-xs hover:opacity-70">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Live FHIR Tester Drawer / Collapsible Box */}
      {showFhirTester && (
        <div className="p-5 rounded-2xl bg-surface-container border border-primary/30 space-y-4 shadow-md transition-all">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="p-1.5 bg-primary text-white rounded-lg">
                <Server className="w-4 h-4" />
              </span>
              <div>
                <h4 className="text-sm font-bold text-on-surface">Interactive SMART on FHIR R4 Diagnostic Tool</h4>
                <p className="text-xs text-on-surface-variant">
                  Perform real-time CapabilityStatement latency testing and resource inspection against any FHIR R4 server.
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowFhirTester(false)}
              className="text-xs text-on-surface-variant hover:text-on-surface p-1 rounded-lg hover:bg-surface-container-high"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-2">
              <label className="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant mb-1 block">
                FHIR R4 Server Base URL
              </label>
              <input
                type="text"
                value={fhirTestUrl}
                onChange={(e) => setFhirTestUrl(e.target.value)}
                placeholder="https://hapi.fhir.org/baseR4"
                className="w-full px-3 py-2 text-xs font-mono rounded-xl bg-surface border border-surface-container-high focus:outline-none focus:border-primary"
              />
            </div>
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant mb-1 block">
                Bearer Token (Optional)
              </label>
              <input
                type="password"
                value={fhirTestToken}
                onChange={(e) => setFhirTestToken(e.target.value)}
                placeholder="Bearer token if secured"
                className="w-full px-3 py-2 text-xs font-mono rounded-xl bg-surface border border-surface-container-high focus:outline-none focus:border-primary"
              />
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
            <div className="flex items-center gap-2 text-[11px] text-on-surface-variant">
              <span>Quick Presets:</span>
              <button
                type="button"
                onClick={() => setFhirTestUrl("https://hapi.fhir.org/baseR4")}
                className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface hover:bg-primary/20 hover:text-primary font-mono text-[10px]"
              >
                HAPI FHIR R4
              </button>
              <button
                type="button"
                onClick={() => setFhirTestUrl("https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4")}
                className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface hover:bg-primary/20 hover:text-primary font-mono text-[10px]"
              >
                Epic Interconnect
              </button>
              <button
                type="button"
                onClick={() => setFhirTestUrl("https://fhir-myrecord.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d")}
                className="px-2 py-0.5 rounded bg-surface-container-high text-on-surface hover:bg-primary/20 hover:text-primary font-mono text-[10px]"
              >
                Cerner R4
              </button>
            </div>

            <button
              onClick={handleRunFhirDiagnostic}
              disabled={fhirTestLoading || !fhirTestUrl}
              className="px-4 py-1.5 rounded-xl text-xs font-bold bg-primary text-white hover:bg-primary/90 flex items-center gap-1.5 disabled:opacity-50"
            >
              {fhirTestLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5" />}
              <span>Inspect FHIR Endpoint</span>
            </button>
          </div>

          {/* Diagnostic Output */}
          {fhirTestResult && (
            <div
              className={`p-4 rounded-xl text-xs border ${
                fhirTestResult.online
                  ? "bg-[#edf7e0] text-[#1e3e00] border-[#7FCD4D]/40"
                  : "bg-[#fce4ec] text-[#b71c1c] border-rose-200"
              }`}
            >
              <div className="flex items-center justify-between font-bold mb-2">
                <div className="flex items-center gap-1.5">
                  {fhirTestResult.online ? <CheckCircle2 className="w-4 h-4 text-[#396a00]" /> : <AlertCircle className="w-4 h-4 text-[#b71c1c]" />}
                  <span>{fhirTestResult.message}</span>
                </div>
                {fhirTestResult.latency_ms && (
                  <span className="font-mono text-[11px] px-2 py-0.5 bg-white/70 rounded-full">
                    Latency: {fhirTestResult.latency_ms}ms
                  </span>
                )}
              </div>

              {fhirTestResult.online && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-[11px]">
                  <div className="bg-white/60 p-2 rounded-lg">
                    <span className="text-on-surface-variant block text-[10px]">FHIR Version</span>
                    <span className="font-bold">{fhirTestResult.fhir_version || "R4 (4.0.1)"}</span>
                  </div>
                  <div className="bg-white/60 p-2 rounded-lg">
                    <span className="text-on-surface-variant block text-[10px]">Server Software</span>
                    <span className="font-bold truncate block">{fhirTestResult.software_name || "FHIR Engine"}</span>
                  </div>
                  <div className="bg-white/60 p-2 rounded-lg">
                    <span className="text-on-surface-variant block text-[10px]">Resource Types</span>
                    <span className="font-bold">{fhirTestResult.total_resources || 0} Supported</span>
                  </div>
                  <div className="bg-white/60 p-2 rounded-lg">
                    <span className="text-on-surface-variant block text-[10px]">HTTP Status</span>
                    <span className="font-bold">{fhirTestResult.status_code || 200} OK</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
        {/* Category Tabs */}
        <div className="flex flex-wrap items-center gap-1.5 overflow-x-auto pb-1">
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all whitespace-nowrap ${
                activeCategory === cat
                  ? "bg-primary text-white shadow-sm font-bold"
                  : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Search Field */}
        <div className="relative min-w-[220px]">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search EHR providers..."
            className="w-full pl-8 pr-3 py-1.5 text-xs rounded-xl bg-surface-container border border-surface-container-high focus:outline-none focus:border-primary text-on-surface"
          />
        </div>
      </div>

      {/* Providers Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredProviders.map((provider) => {
          const integration = integrations.find((i) => i.provider_name === provider.id);
          const isConnected = Boolean(integration && integration.is_active);
          const syncEnabled = integration ? integration.sync_enabled : false;
          const currentFreq = integration?.sync_frequency || "realtime";
          const lastSyncedAt = integration?.last_synced_at;
          const isTesting = syncingProvider === provider.id;

          return (
            <div
              key={provider.id}
              className={`p-5 rounded-2xl bg-surface-container border transition-all flex flex-col justify-between ${
                isConnected
                  ? "border-[#7FCD4D]/40 bg-surface-container-low shadow-sm"
                  : "border-surface-container opacity-95"
              }`}
            >
              <div>
                {/* Header with Provider Info */}
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant">
                        {provider.category}
                      </span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-surface-container-high text-on-surface-variant">
                        {provider.badge}
                      </span>
                    </div>
                    <h4 className="text-base font-bold text-on-surface mt-1">{provider.name}</h4>
                  </div>

                  {/* Status Badge */}
                  {isConnected ? (
                    <span className="bg-[#edf7e0] text-[#396a00] text-[11px] font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-[#396a00] animate-pulse" />
                      Connected
                    </span>
                  ) : (
                    <span className="bg-surface-container-high text-on-surface-variant text-[11px] font-semibold px-2 py-0.5 rounded-full">
                      Disconnected
                    </span>
                  )}
                </div>

                <p className="text-xs text-on-surface-variant line-clamp-2 mb-4 leading-relaxed">
                  {provider.description}
                </p>

                {/* Connected Settings Controls */}
                {isConnected && (
                  <div className="space-y-3 pt-2 pb-3 border-t border-surface-container-high/60">
                    {/* Sync Enabled Switch */}
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-on-surface flex items-center gap-1.5">
                        <Zap className={`w-3.5 h-3.5 ${syncEnabled ? "text-primary" : "text-on-surface-variant"}`} />
                        Auto-Sync Active
                      </span>
                      <button
                        type="button"
                        onClick={() => handlePatchToggleSync(provider.id, syncEnabled)}
                        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                          syncEnabled ? "bg-primary" : "bg-surface-container-highest"
                        }`}
                      >
                        <span
                          className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                            syncEnabled ? "translate-x-4" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>

                    {/* Sync Frequency Selector */}
                    <div>
                      <label className="text-[10px] font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                        Sync Frequency
                      </label>
                      <select
                        value={currentFreq}
                        onChange={(e) => handlePatchFrequency(provider.id, e.target.value)}
                        className="w-full px-2.5 py-1.5 text-xs rounded-xl bg-surface border border-surface-container-high font-medium text-on-surface focus:outline-none focus:border-primary"
                      >
                        {SYNC_FREQUENCY_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Last Sync Timestamp */}
                    <div className="flex items-center justify-between text-[11px] text-on-surface-variant pt-1">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Last Synced:
                      </span>
                      <span className="font-mono text-on-surface font-semibold">
                        {lastSyncedAt ? new Date(lastSyncedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Ready"}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Action Buttons Footer */}
              <div className="pt-3 border-t border-surface-container flex items-center gap-2">
                {isConnected ? (
                  <>
                    <button
                      onClick={() => handleVerifySaved(provider.id, provider.name)}
                      disabled={isTesting}
                      className="btn-secondary flex-1 py-1.5 text-xs flex items-center justify-center gap-1.5 font-bold"
                    >
                      {isTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5" />}
                      Test
                    </button>

                    <button
                      onClick={() => openConfigModal(provider)}
                      className="p-1.5 rounded-xl border border-surface-container-high hover:bg-surface-container text-on-surface transition-colors"
                      title="Edit Credentials"
                    >
                      <Settings className="w-4 h-4" />
                    </button>

                    <button
                      onClick={() => handleDisconnect(provider.id, provider.name)}
                      className="p-1.5 border border-rose-300/40 rounded-xl hover:bg-rose-50 text-rose-600 transition-colors"
                      title="Disconnect Integration"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </>
                ) : (
                  <div className="flex items-center gap-2 w-full">
                    <button
                      onClick={() => openConfigModal(provider)}
                      className="btn-primary flex-1 py-2 text-xs flex items-center justify-center gap-1.5 font-bold"
                    >
                      <Sliders className="w-3.5 h-3.5" />
                      Configure & Connect
                    </button>
                    {provider.docsUrl && (
                      <a
                        href={provider.docsUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="p-2 rounded-xl border border-surface-container-high hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors"
                        title="View Documentation"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Provider Configuration Modal */}
      {editingProvider && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-surface rounded-2xl max-w-xl w-full p-6 border border-surface-container-high shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-surface-container pb-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] uppercase font-bold tracking-wider text-primary px-2 py-0.5 bg-primary/10 rounded-full">
                    {editingProvider.category}
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 bg-surface-container-high rounded text-on-surface-variant">
                    {editingProvider.badge}
                  </span>
                </div>
                <h3 className="text-lg font-extrabold text-on-surface mt-1">
                  Configure {editingProvider.name}
                </h3>
                <p className="text-xs text-on-surface-variant mt-0.5">
                  Set API credentials and synchronization policies for this EHR provider.
                </p>
              </div>
              <button
                onClick={closeConfigModal}
                className="p-1 rounded-xl text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Status Notice */}
            {modalStatus && (
              <div
                className={`p-3 rounded-xl text-xs font-semibold flex items-center gap-2 ${
                  modalStatus.type === "success"
                    ? "bg-[#edf7e0] text-[#396a00] border border-[#7FCD4D]/40"
                    : "bg-[#fce4ec] text-[#b71c1c] border border-rose-200"
                }`}
              >
                {modalStatus.type === "success" ? (
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                ) : (
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                )}
                <span>{modalStatus.text}</span>
              </div>
            )}

            {/* Form Fields */}
            <form onSubmit={handleSaveModal} className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[55vh] overflow-y-auto pr-1">
                {editingProvider.fields.map((field) => {
                  const isPassword = field.type === "password";
                  const showPass = Boolean(showPasswords[field.key]);

                  return (
                    <div key={field.key} className={field.key === "fhir_endpoint" || field.key === "webhook_secret" || field.key === "access_token" ? "sm:col-span-2" : ""}>
                      <div className="flex items-center justify-between mb-1">
                        <label className="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
                          {field.label}
                        </label>
                        {field.defaultVal && (
                          <button
                            type="button"
                            onClick={() => setFormData((prev) => ({ ...prev, [field.key]: field.defaultVal }))}
                            className="text-[10px] text-primary hover:underline"
                          >
                            Default
                          </button>
                        )}
                      </div>

                      <div className="relative">
                        <input
                          type={isPassword ? (showPass ? "text" : "password") : field.type}
                          value={formData[field.key] || ""}
                          onChange={(e) => setFormData((prev) => ({ ...prev, [field.key]: e.target.value }))}
                          placeholder={field.placeholder}
                          className="w-full px-3 py-2 text-xs font-mono rounded-xl bg-surface-container border border-surface-container-high text-on-surface focus:outline-none focus:border-primary pr-9"
                        />
                        {isPassword && (
                          <button
                            type="button"
                            onClick={() => togglePasswordVisibility(field.key)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant hover:text-on-surface"
                          >
                            {showPass ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                          </button>
                        )}
                      </div>
                      {field.hint && (
                        <p className="text-[10px] text-on-surface-variant mt-1">{field.hint}</p>
                      )}
                    </div>
                  );
                })}

                {/* Sync Frequency in Modal */}
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                    Default Sync Frequency
                  </label>
                  <select
                    value={formData.sync_frequency || "realtime"}
                    onChange={(e) => setFormData((prev) => ({ ...prev, sync_frequency: e.target.value }))}
                    className="w-full px-3 py-2 text-xs rounded-xl bg-surface-container border border-surface-container-high font-medium text-on-surface focus:outline-none focus:border-primary"
                  >
                    {SYNC_FREQUENCY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Sync Active in Modal */}
                <div className="flex items-center justify-between sm:pt-6">
                  <div>
                    <span className="text-xs font-bold text-on-surface block">Enable Auto Sync</span>
                    <span className="text-[10px] text-on-surface-variant">Sync records automatically</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setFormData((prev) => ({ ...prev, sync_enabled: !prev.sync_enabled }))}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                      formData.sync_enabled ? "bg-primary" : "bg-surface-container-highest"
                    }`}
                  >
                    <span
                      className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                        formData.sync_enabled ? "translate-x-4" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              </div>

              {/* Modal Footer Action Buttons */}
              <div className="flex items-center justify-between gap-3 pt-4 border-t border-surface-container">
                <button
                  type="button"
                  onClick={handleTestModalConnection}
                  disabled={modalTesting}
                  className="btn-secondary px-4 py-2 text-xs font-bold flex items-center gap-1.5"
                >
                  {modalTesting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wifi className="w-3.5 h-3.5" />}
                  Test Connection
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={closeConfigModal}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-on-surface-variant hover:bg-surface-container transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={modalSaving}
                    className="btn-primary px-5 py-2 text-xs font-bold flex items-center gap-1.5"
                  >
                    {modalSaving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Save & Activate
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default EhrSettings;
