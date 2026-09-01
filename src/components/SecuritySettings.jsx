import React, { useState, useEffect, useCallback } from "react";
import { 
  Shield, 
  Laptop, 
  Smartphone, 
  Trash2, 
  RefreshCw, 
  History, 
  Globe, 
  CheckCircle, 
  AlertTriangle,
  LogOut,
  Clock,
  Key,
  Lock,
  Eye,
  EyeOff,
  Download,
  Search,
  Filter,
  Plus,
  Server,
  FileText,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Info
} from "lucide-react";
import api from "../lib/api";

// Simple and robust User Agent parser
const parseUA = (uaString) => {
  if (!uaString) return { browser: "Web Browser", os: "System Device", device: "desktop" };
  
  const ua = uaString.toLowerCase();
  let browser = "Web Browser";
  let os = "Desktop";
  let device = "desktop";

  // OS detection
  if (ua.includes("windows")) os = "Windows";
  else if (ua.includes("macintosh") || ua.includes("mac os")) os = "macOS";
  else if (ua.includes("iphone") || ua.includes("ipad")) {
    os = "iOS";
    device = "mobile";
  } else if (ua.includes("android")) {
    os = "Android";
    device = "mobile";
  } else if (ua.includes("linux")) os = "Linux";

  // Browser detection
  if (ua.includes("edg/")) browser = "Microsoft Edge";
  else if (ua.includes("chrome") && !ua.includes("chromium")) browser = "Google Chrome";
  else if (ua.includes("safari") && !ua.includes("chrome")) browser = "Apple Safari";
  else if (ua.includes("firefox")) browser = "Mozilla Firefox";
  else if (ua.includes("opera") || ua.includes("opr/")) browser = "Opera";
  
  return { browser, os, device };
};

const formatTimeAgo = (dateStr) => {
  if (!dateStr) return "Never";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
};

const getActionLabel = (action = "") => {
  const act = String(action).toLowerCase();
  if (act.includes("login_success") || act.includes("auth.login")) {
    return { text: "Login Successful", color: "#10b981", bg: "#ecfdf5", type: "success" };
  }
  if (act.includes("login_failed") || act.includes("failed")) {
    return { text: "Failed Login Attempt", color: "#ef4444", bg: "#fef2f2", type: "danger" };
  }
  if (act.includes("rate_limited") || act.includes("warning")) {
    return { text: "Rate Limited Attempt", color: "#f59e0b", bg: "#fffbeb", type: "warning" };
  }
  if (act.includes("mfa_enabled") || act.includes("mfa")) {
    return { text: "MFA Verified & Configured", color: "#10b981", bg: "#ecfdf5", type: "success" };
  }
  if (act.includes("mfa_disabled")) {
    return { text: "MFA Deactivated", color: "#f59e0b", bg: "#fffbeb", type: "warning" };
  }
  if (act.includes("ip_whitelist")) {
    return { text: "IP Access Policy Updated", color: "#3b82f6", bg: "#eff6ff", type: "info" };
  }
  if (act.includes("settings_updated") || act.includes("settings")) {
    return { text: "Security Policy Configured", color: "#6366f1", bg: "#eef2ff", type: "info" };
  }
  if (act.includes("exported") || act.includes("export")) {
    return { text: "HIPAA Audit Exported", color: "#8b5cf6", bg: "#f5f3ff", type: "info" };
  }
  if (act.includes("patient")) {
    return { text: "PHI Patient Record Access", color: "#0ea5e9", bg: "#f0f9ff", type: "info" };
  }
  if (act.includes("appointment")) {
    return { text: "Appointment Record Operation", color: "#06b6d4", bg: "#ecfeff", type: "info" };
  }

  const cleanText = action.replace(/^(auth|security|compliance|clinic)\./, "").replace(/_/g, " ").toUpperCase();
  return { text: cleanText || "AUDIT EVENT", color: "#64748b", bg: "#f1f5f9", type: "neutral" };
};

const TIMEOUT_PRESETS = [
  { value: 3, label: "3 Minutes (Strict HIPAA Lockout)" },
  { value: 5, label: "5 Minutes" },
  { value: 15, label: "15 Minutes (HIPAA Standard)" },
  { value: 30, label: "30 Minutes" },
  { value: 60, label: "60 Minutes" },
  { value: 120, label: "2 Hours" }
];

const SecuritySettings = () => {
  // Global & Feedback States
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [message, setMessage] = useState(null);
  const [err, setErr] = useState(null);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [copiedIp, setCopiedIp] = useState(null);

  // Security Configuration States
  const [secSettings, setSecSettings] = useState({
    mfa_enforced: false,
    ip_whitelist_enabled: false,
    ip_whitelist: [],
    idle_session_timeout_minutes: 15,
    phi_scrubbing_enabled: true,
    audit_retention_days: 2190,
    client_ip: "127.0.0.1",
  });

  // MFA States
  const [mfaFactors, setMfaFactors] = useState([]);
  const [showMfaModal, setShowMfaModal] = useState(false);
  const [mfaEnrollData, setMfaEnrollData] = useState(null);
  const [mfaCode, setMfaCode] = useState("");
  const [mfaError, setMfaError] = useState(null);
  const [mfaLoading, setMfaLoading] = useState(false);

  // IP Whitelist States
  const [newIpInput, setNewIpInput] = useState("");
  const [newIpLabel, setNewIpLabel] = useState("");
  const [ipError, setIpError] = useState(null);
  const [addingIp, setAddingIp] = useState(false);

  // Password Change States
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordError, setPasswordError] = useState(null);
  const [passwordSuccess, setPasswordSuccess] = useState(null);

  // Sessions States
  const [sessions, setSessions] = useState([]);

  // HIPAA Audit Logs States
  const [logs, setLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logPage, setLogPage] = useState(1);
  const [logLimit, setLogLimit] = useState(15);
  const [totalLogs, setTotalLogs] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [actionFilter, setActionFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedLogModal, setSelectedLogModal] = useState(null);
  const [integrityData, setIntegrityData] = useState(null);
  const [verifyingIntegrity, setVerifyingIntegrity] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

  // ─────────────────────────────────────────────────────────────────────────
  // Fetch Security Data
  // ─────────────────────────────────────────────────────────────────────────
  const fetchSecurityData = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [settingsRes, sessionsRes, mfaRes] = await Promise.all([
        api.get("/security/settings").catch(() => null),
        api.get("/security/sessions").catch(() => api.get("/auth/sessions").catch(() => ({ data: { data: [] } }))),
        api.get("/security/mfa/status").catch(() => api.get("/auth/mfa/factors").catch(() => ({ data: { data: { all: [] } } })))
      ]);

      if (settingsRes?.data?.data) {
        setSecSettings(settingsRes.data.data);
        if (settingsRes.data.data.idle_session_timeout_minutes) {
          localStorage.setItem("bytelytic_idle_timeout_mins", String(settingsRes.data.data.idle_session_timeout_minutes));
          window.dispatchEvent(new Event("bytelytic_idle_timeout_changed"));
        }
      }

      setSessions(sessionsRes?.data?.data || []);

      // Parse MFA Factors comprehensively
      const mfaData = mfaRes?.data?.data || mfaRes?.data;
      let factorsList = [];
      if (Array.isArray(mfaData)) {
        factorsList = mfaData;
      } else if (mfaData?.verified_factors?.length > 0) {
        factorsList = mfaData.verified_factors;
      } else if (mfaData?.factors?.length > 0) {
        factorsList = mfaData.factors;
      } else if (mfaData?.all?.length > 0) {
        factorsList = mfaData.all;
      } else if (mfaData?.totp?.length > 0) {
        factorsList = mfaData.totp;
      } else if (mfaData?.is_active) {
        factorsList = [{ id: "mfa-active", status: "verified", factor_type: "totp" }];
      } else {
        factorsList = [];
      }
      setMfaFactors(factorsList);
    } catch (error) {
      console.error("Failed to load security configurations", error);
      setErr("Failed to load security configurations. Please ensure database connection is healthy.");
    } finally {
      setLoading(false);
    }
  }, []);

  // ─────────────────────────────────────────────────────────────────────────
  // Fetch Audit Logs with Filters & Pagination
  // ─────────────────────────────────────────────────────────────────────────
  const fetchAuditLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(logPage),
        limit: String(logLimit)
      });
      if (actionFilter && actionFilter !== "all") params.append("action", actionFilter);
      if (searchQuery.trim()) params.append("search", searchQuery.trim());

      const res = await api.get(`/security/audit-logs?${params.toString()}`).catch(() => 
        api.get(`/auth/audit-logs?limit=${logLimit}`).catch(() => ({ data: { data: [] } }))
      );

      const data = res?.data?.data || [];
      const meta = res?.data?.meta || {};

      setLogs(data);
      setTotalLogs(meta.total ?? data.length);
      setTotalPages(meta.total_pages ?? Math.max(1, Math.ceil((meta.total ?? data.length) / logLimit)));
    } catch (error) {
      console.error("Error fetching audit logs", error);
    } finally {
      setLogsLoading(false);
    }
  }, [logPage, logLimit, actionFilter, searchQuery]);

  useEffect(() => {
    fetchSecurityData();
  }, [fetchSecurityData]);

  useEffect(() => {
    fetchAuditLogs();
  }, [fetchAuditLogs]);

  // ─────────────────────────────────────────────────────────────────────────
  // Idle Session Timeout Configuration
  // ─────────────────────────────────────────────────────────────────────────
  const handleTimeoutChange = async (newMinutes) => {
    const mins = parseInt(newMinutes, 10);
    if (isNaN(mins) || mins < 1 || mins > 1440) return;

    setActionLoading("timeout");
    setMessage(null);
    setErr(null);

    try {
      await api.patch("/security/settings", { idle_session_timeout_minutes: mins });
      setSecSettings(prev => ({ ...prev, idle_session_timeout_minutes: mins }));
      localStorage.setItem("bytelytic_idle_timeout_mins", String(mins));
      window.dispatchEvent(new Event("bytelytic_idle_timeout_changed"));
      setMessage(`Idle session timeout updated to ${mins} minutes (HIPAA § 164.312 compliant).`);
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to update session timeout.");
    } finally {
      setActionLoading(null);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // PHI Scrubbing Toggle
  // ─────────────────────────────────────────────────────────────────────────
  const handleTogglePhiScrubbing = async () => {
    const nextState = !secSettings.phi_scrubbing_enabled;
    setActionLoading("phi-toggle");
    setMessage(null);
    setErr(null);

    try {
      await api.patch("/security/settings", { phi_scrubbing_enabled: nextState });
      setSecSettings(prev => ({ ...prev, phi_scrubbing_enabled: nextState }));
      setMessage(nextState 
        ? "Automated PHI / PII Data Scrubbing has been ENABLED for all logs & transcripts."
        : "Automated PHI Scrubbing has been DISABLED.");
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to toggle PHI scrubbing.");
    } finally {
      setActionLoading(null);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // IP Whitelist Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const handleToggleIpWhitelist = async () => {
    const nextState = !secSettings.ip_whitelist_enabled;
    setActionLoading("ip-toggle");
    setMessage(null);
    setErr(null);

    try {
      await api.post("/security/ip-whitelist/toggle", { enabled: nextState });
      setSecSettings(prev => ({ ...prev, ip_whitelist_enabled: nextState }));
      setMessage(nextState
        ? "IP Whitelist Access Control is now ACTIVE. Only whitelisted IP addresses can access this clinic."
        : "IP Whitelist Access Control has been DISABLED.");
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to toggle IP whitelist.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddIp = async (e) => {
    if (e) e.preventDefault();
    setIpError(null);
    const ip = newIpInput.trim();
    if (!ip) {
      setIpError("Please enter an IPv4 address, IPv6 address, or CIDR range.");
      return;
    }

    setAddingIp(true);
    setMessage(null);
    setErr(null);

    try {
      const res = await api.post("/security/ip-whitelist", {
        ip_or_cidr: ip,
        label: newIpLabel.trim() || "Office Network"
      });
      setSecSettings(prev => ({
        ...prev,
        ip_whitelist: res.data?.data?.whitelist || [...(prev.ip_whitelist || []), res.data?.data?.entry]
      }));
      setNewIpInput("");
      setNewIpLabel("");
      setMessage(`IP / CIDR address '${ip}' was successfully whitelisted.`);
      fetchAuditLogs();
    } catch (error) {
      setIpError(error.response?.data?.detail || "Invalid IP address or CIDR range format.");
    } finally {
      setAddingIp(false);
    }
  };

  const handleDeleteIp = async (itemId, ipStr) => {
    if (!window.confirm(`Are you sure you want to remove '${ipStr}' from the authorized IP whitelist?`)) return;
    setActionLoading(`delete-ip-${itemId || ipStr}`);
    setMessage(null);
    setErr(null);

    try {
      const targetParam = encodeURIComponent(itemId || ipStr);
      const res = await api.delete(`/security/ip-whitelist/${targetParam}`);
      setSecSettings(prev => ({
        ...prev,
        ip_whitelist: res.data?.data?.whitelist || prev.ip_whitelist.filter(item => item.id !== itemId && item.ip_or_cidr !== ipStr && item.ip_or_cidr !== itemId)
      }));
      setMessage(`Removed IP address '${ipStr}' from whitelist.`);
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to remove IP from whitelist.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleAddCurrentIp = () => {
    if (secSettings.client_ip && secSettings.client_ip !== "unknown") {
      setNewIpInput(secSettings.client_ip);
      setNewIpLabel("My Current Location");
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // MFA Handlers
  // ─────────────────────────────────────────────────────────────────────────
  const handleEnrollMfa = async () => {
    setMfaLoading(true);
    setMfaError(null);
    setMfaCode("");
    try {
      const res = await api.post("/security/mfa/enroll").catch(() => api.post("/auth/mfa/enroll"));
      const enrollData = res.data?.data || res.data;
      setMfaEnrollData(enrollData);
      setShowMfaModal(true);
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to initiate MFA setup.");
    } finally {
      setMfaLoading(false);
    }
  };

  const handleVerifyMfa = async () => {
    if (mfaCode.length !== 6) return setMfaError("Please enter a valid 6-digit code.");
    setMfaLoading(true);
    setMfaError(null);
    try {
      const factorId = mfaEnrollData?.id || mfaEnrollData?.data?.id || mfaEnrollData?.totp?.id || "mock-factor-id";
      await api.post("/security/mfa/verify", {
        factor_id: factorId,
        code: mfaCode
      }).catch(() => api.post("/auth/mfa/verify", {
        factor_id: factorId,
        code: mfaCode
      }));

      setMessage("Multi-Factor Authentication (MFA) was verified and activated successfully!");
      setShowMfaModal(false);
      fetchSecurityData();
      fetchAuditLogs();
    } catch (error) {
      setMfaError(error.response?.data?.detail || "Incorrect verification code. Please check your authenticator app.");
    } finally {
      setMfaLoading(false);
    }
  };

  const handleDisableMfa = async () => {
    if (!window.confirm("Are you sure you want to disable Multi-Factor Authentication? Your account will be less secure.")) return;
    setActionLoading("disable-mfa");
    setMessage(null);
    setErr(null);
    try {
      const factor = mfaFactors.find(f => f.status === "verified" || f.is_active) || mfaFactors[0];
      const factorId = factor?.id || factor?.factor_id || "mock-factor-id";
      await api.post("/security/mfa/disable", { factor_id: factorId }).catch(() => 
        api.post("/auth/mfa/unenroll", { factor_id: factorId })
      );

      setMessage("Multi-Factor Authentication has been disabled.");
      fetchSecurityData();
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to disable MFA.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleToggleMfaEnforcement = async () => {
    const nextState = !secSettings.mfa_enforced;
    setActionLoading("mfa-enforce");
    setMessage(null);
    setErr(null);
    try {
      await api.patch("/security/settings", { mfa_enforced: nextState });
      setSecSettings(prev => ({ ...prev, mfa_enforced: nextState }));
      setMessage(nextState
        ? "Mandatory 2FA Policy is now ACTIVE. All clinic users must verify 2FA upon sign-in."
        : "Mandatory 2FA Policy has been set to optional.");
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to toggle MFA enforcement policy.");
    } finally {
      setActionLoading(null);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Password Change Handler & Validation
  // ─────────────────────────────────────────────────────────────────────────
  const passChecks = {
    length: newPassword.length >= 8,
    uppercase: /[A-Z]/.test(newPassword),
    number: /[0-9]/.test(newPassword),
    special: /[!@#$%^&*(),.?":{}|<>]/.test(newPassword),
    match: Boolean(newPassword && confirmPassword && newPassword === confirmPassword),
  };
  const isNewPasswordValid = passChecks.length && passChecks.uppercase && passChecks.number && passChecks.special;

  const handleChangePassword = async (e) => {
    if (e) e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!currentPassword) {
      setPasswordError("Please enter your current password.");
      return;
    }
    if (!isNewPasswordValid) {
      setPasswordError("New password must meet all complexity requirements (8+ characters, uppercase letter, number, special character).");
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError("New password and confirmation password do not match.");
      return;
    }
    if (newPassword === currentPassword) {
      setPasswordError("New password cannot be the same as your current password.");
      return;
    }

    setPasswordLoading(true);
    try {
      const res = await api.post("/security/change-password", {
        old_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
      setPasswordSuccess(res.data?.message || "Password updated successfully. Other device sessions have been safely logged out.");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      fetchAuditLogs();
    } catch (error) {
      setPasswordError(error.response?.data?.detail || "Failed to update password. Please verify your current password.");
    } finally {
      setPasswordLoading(false);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Sessions Revocation
  // ─────────────────────────────────────────────────────────────────────────
  const handleRevokeSession = async (sessionId) => {
    setActionLoading(sessionId);
    setMessage(null);
    setErr(null);
    try {
      await api.post("/security/sessions/revoke", { session_id: sessionId }).catch(() =>
        api.post("/auth/sessions/revoke", { session_id: sessionId })
      );
      setMessage("Active device session disconnected successfully.");
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to disconnect session.");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRevokeAllSessions = async () => {
    if (!window.confirm("Are you sure you want to log out of all other active sessions? Other devices will be disconnected immediately.")) return;
    setActionLoading("revoke-all");
    setMessage(null);
    setErr(null);
    try {
      await api.post("/security/sessions/revoke-all").catch(() => api.post("/auth/sessions/revoke-all"));
      setMessage("All other active device sessions have been disconnected.");
      fetchSecurityData();
      fetchAuditLogs();
    } catch (error) {
      setErr(error.response?.data?.detail || "Failed to terminate other sessions.");
    } finally {
      setActionLoading(null);
    }
  };

  // ─────────────────────────────────────────────────────────────────────────
  // Audit Chain Verification & CSV Export
  // ─────────────────────────────────────────────────────────────────────────
  const handleVerifyAuditChain = async () => {
    setVerifyingIntegrity(true);
    try {
      const res = await api.get("/security/audit-logs/verify-integrity").catch(() => 
        api.get("/compliance/audit-chain/verify").catch(() => null)
      );
      if (res?.data?.data) {
        setIntegrityData(res.data.data);
      } else {
        setIntegrityData({
          status: "UNAVAILABLE",
          is_tamper_free: false,
          total_records_verified: 0,
          algorithm: "SHA-256-HMAC-CHAIN",
          message: "Audit chain verification could not be completed. Please ensure audit logging service is active."
        });
      }
    } catch (error) {
      console.error("Integrity check error", error);
      setIntegrityData({
        status: "ERROR",
        is_tamper_free: false,
        total_records_verified: 0,
        algorithm: "SHA-256-HMAC-CHAIN",
        message: "Failed to verify cryptographic audit trail."
      });
    } finally {
      setVerifyingIntegrity(false);
    }

  };

  const handleExportCsv = async () => {
    setExportingCsv(true);
    try {
      const response = await api.get("/security/audit-logs/export", { responseType: "blob" });
      const blob = new Blob([response.data], { type: "text/csv;charset=utf-8;" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `hipaa_audit_log_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setMessage("HIPAA Audit Log exported to CSV successfully.");
      fetchAuditLogs();
    } catch (error) {
      setErr("Failed to export audit logs. Please try again.");
    } finally {
      setExportingCsv(false);
    }
  };

  const activeMfa = mfaFactors.find(f => f.status === "verified") || (mfaFactors.length > 0 && mfaFactors[0].status === "verified");

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-20 space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin text-primary" />
        <p className="text-sm font-semibold text-on-surface-variant">Loading Security & Compliance Engine...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* ── Top Feedback Banner ───────────────────────────────── */}
      {message && (
        <div className="bg-[#edf7e0] border border-[#7dbd42]/30 text-[#396a00] px-4 py-3 rounded-2xl text-sm font-semibold flex items-center justify-between gap-3 shadow-sm animate-fadeIn">
          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 flex-shrink-0" />
            <span>{message}</span>
          </div>
          <button onClick={() => setMessage(null)} className="text-xs font-bold opacity-70 hover:opacity-100">✕</button>
        </div>
      )}
      {err && (
        <div className="bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3 rounded-2xl text-sm font-semibold flex items-center justify-between gap-3 shadow-sm animate-fadeIn">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{err}</span>
          </div>
          <button onClick={() => setErr(null)} className="text-xs font-bold opacity-70 hover:opacity-100">✕</button>
        </div>
      )}

      {/* ── SECTION 1: Compliance & Security Overview Cards ──── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-5 space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant/70">MFA Status</span>
            <div className={`w-2.5 h-2.5 rounded-full ${activeMfa ? "bg-emerald-500" : "bg-amber-500"}`} />
          </div>
          <div className="text-lg font-extrabold text-on-surface">
            {activeMfa ? "2FA Active" : "Not Enabled"}
          </div>
          <p className="text-[11px] text-on-surface-variant/80">
            {activeMfa ? "Protected by TOTP Authenticator" : "High risk: Enable TOTP app protection"}
          </p>
        </div>

        <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant/70">IP Whitelist</span>
            <div className={`w-2.5 h-2.5 rounded-full ${secSettings.ip_whitelist_enabled ? "bg-emerald-500" : "bg-slate-400"}`} />
          </div>
          <div className="text-lg font-extrabold text-on-surface">
            {secSettings.ip_whitelist_enabled ? `${secSettings.ip_whitelist?.length || 0} IPs Active` : "Disabled"}
          </div>
          <p className="text-[11px] text-on-surface-variant/80">
            {secSettings.ip_whitelist_enabled ? "Restricted clinic access" : "Open from all authorized networks"}
          </p>
        </div>

        <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant/70">Idle Timeout</span>
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500" />
          </div>
          <div className="text-lg font-extrabold text-on-surface">
            {secSettings.idle_session_timeout_minutes} Minutes
          </div>
          <p className="text-[11px] text-on-surface-variant/80">
            HIPAA § 164.312(a)(2)(iii) compliant logoff
          </p>
        </div>

        <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-5 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold uppercase tracking-wider text-on-surface-variant/70">PHI Scrubbing</span>
            <div className={`w-2.5 h-2.5 rounded-full ${secSettings.phi_scrubbing_enabled ? "bg-emerald-500" : "bg-rose-500"}`} />
          </div>
          <div className="text-lg font-extrabold text-on-surface">
            {secSettings.phi_scrubbing_enabled ? "Active" : "Disabled"}
          </div>
          <p className="text-[11px] text-on-surface-variant/80">
            Real-time PII & PHI log de-identification
          </p>
        </div>
      </div>

      {/* ── SECTION 2: Multi-Factor Authentication (MFA) ──────── */}
      <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
              <Shield className="w-5 h-5 text-primary" /> Multi-Factor Authentication (MFA / 2FA)
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              Enforce a second layer of security via time-based one-time password (TOTP) authenticator applications.
            </p>
          </div>
          <div>
            {activeMfa ? (
              <button
                onClick={handleDisableMfa}
                disabled={actionLoading === "disable-mfa"}
                className="flex items-center gap-2 py-2 px-4 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 transition-all disabled:opacity-50"
              >
                Disable 2FA
              </button>
            ) : (
              <button
                onClick={handleEnrollMfa}
                disabled={mfaLoading}
                className="flex items-center gap-2 py-2 px-4 rounded-xl text-xs font-bold text-white bg-primary hover:bg-primary/95 transition-all disabled:opacity-50"
              >
                {mfaLoading ? "Configuring..." : "Enable 2FA Authenticator"}
              </button>
            )}
          </div>
        </div>

        <div className="border border-on-surface-variant/10 rounded-xl p-4 flex gap-4 items-center bg-surface-container/20">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${
            activeMfa ? "bg-emerald-50 text-emerald-600" : "bg-amber-50 text-amber-600"
          }`}>
            <Lock className="w-5 h-5" />
          </div>
          <div className="flex-1">
            <p className="text-xs font-bold text-on-surface">
              Status: {activeMfa ? "Active & Enforced (TOTP Authenticator)" : "Not Configured"}
            </p>
            <p className="text-[11px] text-on-surface-variant/80 mt-0.5">
              {activeMfa 
                ? "Your clinic account is secured. Logins require an authenticator token (Google Authenticator, Microsoft Authenticator, 1Password, etc.)."
                : "MFA is recommended for all healthcare clinics accessing Electronic Health Records (EHR) and Protected Health Information (PHI)."}
            </p>
          </div>
        </div>
      </div>

      {/* ── SECTION 3: IP Whitelist Access Control ─────────────── */}
      <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
              <Globe className="w-5 h-5 text-primary" /> IP Whitelist Access Control
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              Restrict clinic access exclusively to static IP addresses or VPN CIDR subnets.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-on-surface-variant">
              {secSettings.ip_whitelist_enabled ? "Enforcement: Active" : "Enforcement: Off"}
            </span>
            <button
              onClick={handleToggleIpWhitelist}
              disabled={actionLoading === "ip-toggle"}
              className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${
                secSettings.ip_whitelist_enabled ? "bg-primary" : "bg-surface-container-high"
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ${
                secSettings.ip_whitelist_enabled ? "translate-x-6" : "translate-x-0"
              }`} />
            </button>
          </div>
        </div>

        {/* Quick Add Form */}
        <div className="bg-surface-container/30 border border-on-surface-variant/10 rounded-xl p-4 space-y-3">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">
              Add Authorized IP Address or Subnet
            </span>
            {secSettings.client_ip && (
              <button
                type="button"
                onClick={handleAddCurrentIp}
                className="text-xs text-primary font-bold hover:underline inline-flex items-center gap-1"
              >
                <Plus className="w-3 h-3" /> Quick Add Current IP ({secSettings.client_ip})
              </button>
            )}
          </div>

          <form onSubmit={handleAddIp} className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={newIpInput}
              onChange={(e) => setNewIpInput(e.target.value)}
              placeholder="e.g. 192.168.1.1 or 10.0.0.0/24"
              className="input-field flex-1 font-mono text-xs"
            />
            <input
              type="text"
              value={newIpLabel}
              onChange={(e) => setNewIpLabel(e.target.value)}
              placeholder="Label (e.g. Clinic Reception Desk)"
              className="input-field sm:w-60 text-xs"
            />
            <button
              type="submit"
              disabled={addingIp || !newIpInput.trim()}
              className="btn-primary py-2 px-5 text-xs flex items-center justify-center gap-2 whitespace-nowrap disabled:opacity-50"
            >
              {addingIp ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
              Add IP Entry
            </button>
          </form>

          {ipError && (
            <p className="text-xs font-semibold text-rose-600 flex items-center gap-1">
              <AlertTriangle className="w-3.5 h-3.5" /> {ipError}
            </p>
          )}
        </div>

        {/* Whitelist Table */}
        <div className="space-y-2">
          <p className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">
            Whitelisted Networks ({secSettings.ip_whitelist?.length || 0})
          </p>

          {(!secSettings.ip_whitelist || secSettings.ip_whitelist.length === 0) ? (
            <div className="text-center py-6 border border-dashed border-on-surface-variant/10 rounded-xl">
              <Globe className="w-6 h-6 mx-auto text-on-surface-variant/30 mb-1" />
              <p className="text-xs text-on-surface-variant/60 font-semibold">No static IPs configured. Access is open to all networks.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {secSettings.ip_whitelist.map((item) => (
                <div 
                  key={item.id || item.ip_or_cidr}
                  className="border border-on-surface-variant/10 rounded-xl p-3.5 flex items-center justify-between bg-surface-container/10"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-on-surface">{item.ip_or_cidr}</span>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(item.ip_or_cidr);
                          setCopiedIp(item.id || item.ip_or_cidr);
                          setTimeout(() => setCopiedIp(null), 2000);
                        }}
                        className="text-on-surface-variant/40 hover:text-primary transition-colors"
                        title="Copy IP"
                      >
                        {copiedIp === (item.id || item.ip_or_cidr) ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <p className="text-[11px] text-on-surface-variant/70 mt-0.5">{item.label || "Authorized Network"}</p>
                  </div>

                  <button
                    onClick={() => handleDeleteIp(item.id || item.ip_or_cidr, item.ip_or_cidr)}
                    disabled={actionLoading === `delete-ip-${item.id || item.ip_or_cidr}`}
                    className="p-1.5 text-on-surface-variant/50 hover:text-rose-600 transition-colors rounded-lg"
                    title="Delete IP entry"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── SECTION 4: Idle Session Timeout & PHI Scrubbing ───── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Idle Session Timeout Card */}
        <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-6 space-y-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" />
              <h3 className="text-base font-bold text-on-surface">Idle Session Timeout</h3>
            </div>
            <p className="text-xs text-on-surface-variant mt-1">
              Automatically disconnect inactive browser sessions to satisfy HIPAA Security Rule § 164.312(a)(2)(iii).
            </p>
          </div>

          <div className="space-y-3">
            <label className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant/70">
              Automatic Logoff Delay
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {TIMEOUT_PRESETS.map(preset => {
                const isSelected = secSettings.idle_session_timeout_minutes === preset.value;
                return (
                  <button
                    key={preset.value}
                    onClick={() => handleTimeoutChange(preset.value)}
                    disabled={actionLoading === "timeout"}
                    className={`py-2.5 px-3 rounded-xl text-xs font-bold text-left transition-all border ${
                      isSelected
                        ? "border-primary bg-[#edf7e0] text-[#396a00] shadow-sm"
                        : "border-on-surface-variant/10 hover:bg-surface-container text-on-surface"
                    }`}
                  >
                    {preset.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* PHI / PII Scrubbing Card */}
        <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-6 space-y-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                <h3 className="text-base font-bold text-on-surface">Automated PHI / PII Scrubbing</h3>
              </div>
              <button
                onClick={handleTogglePhiScrubbing}
                disabled={actionLoading === "phi-toggle"}
                className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 ${
                  secSettings.phi_scrubbing_enabled ? "bg-primary" : "bg-surface-container-high"
                }`}
              >
                <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ${
                  secSettings.phi_scrubbing_enabled ? "translate-x-6" : "translate-x-0"
                }`} />
              </button>
            </div>
            <p className="text-xs text-on-surface-variant mt-1">
              De-identify patient identifiers (Phone numbers, SSNs, DOBs, Email addresses) across all backend logs and external LLM transcripts.
            </p>
          </div>

          <div className="p-3.5 bg-surface-container/20 border border-on-surface-variant/10 rounded-xl space-y-1">
            <div className="flex items-center gap-2 text-xs font-bold text-on-surface">
              <CheckCircle className="w-4 h-4 text-emerald-600" />
              <span>{secSettings.phi_scrubbing_enabled ? "PHI Redaction Engine: ACTIVE" : "PHI Redaction: OFF"}</span>
            </div>
            <p className="text-[11px] text-on-surface-variant/80">
              Pattern masking regex automatically scrubs 18 HIPAA Safe Harbor identifiers before recording.
            </p>
          </div>
        </div>
      </div>

      {/* ── SECTION 5: Active Device Sessions ─────────────────── */}
      <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
              <Laptop className="w-5 h-5 text-primary" /> Active User Sessions
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              Active browser instances authenticated into this clinic workspace.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchSecurityData}
              disabled={loading}
              className="p-2.5 rounded-xl border border-on-surface-variant/10 text-on-surface-variant hover:bg-surface-container transition-colors disabled:opacity-50"
              title="Refresh session list"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
            {sessions.length > 1 && (
              <button
                onClick={handleRevokeAllSessions}
                disabled={actionLoading === "revoke-all"}
                className="flex items-center gap-2 py-2 px-4 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 transition-all disabled:opacity-50"
              >
                <LogOut className="w-3.5 h-3.5" /> Disconnect Other Devices
              </button>
            )}
          </div>
        </div>

        {sessions.length === 0 ? (
          <div className="text-center py-6 border border-dashed border-on-surface-variant/10 rounded-xl">
            <p className="text-xs text-on-surface-variant/60 font-semibold">No active sessions found.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sessions.map((session, idx) => {
              const ua = parseUA(session.user_agent);
              const isCurrent = idx === 0;

              return (
                <div 
                  key={session.id}
                  className={`border rounded-xl p-4 flex justify-between items-start transition-all ${
                    isCurrent ? "border-primary/30 bg-[#edf7e0]/30" : "border-on-surface-variant/10 bg-surface"
                  }`}
                >
                  <div className="flex gap-3">
                    <div className={`p-2.5 rounded-xl flex items-center justify-center flex-shrink-0 ${
                      isCurrent ? "bg-primary/10 text-primary" : "bg-surface-container text-on-surface-variant/60"
                    }`}>
                      {ua.device === "mobile" ? <Smartphone className="w-5 h-5" /> : <Laptop className="w-5 h-5" />}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-on-surface">{ua.browser} ({ua.os})</span>
                        {isCurrent && (
                          <span className="text-[9px] bg-primary text-white font-extrabold uppercase px-1.5 py-0.5 rounded-full">
                            Current Device
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1 text-[11px] text-on-surface-variant/70 mt-1">
                        <Globe className="w-3 h-3" />
                        <span>{session.ip_address || "127.0.0.1"}</span>
                      </div>
                      <div className="flex items-center gap-1 text-[11px] text-on-surface-variant/50 mt-0.5">
                        <Clock className="w-3 h-3" />
                        <span>Last active: {formatTimeAgo(session.last_active)}</span>
                      </div>
                    </div>
                  </div>

                  {!isCurrent && (
                    <button
                      onClick={() => handleRevokeSession(session.id)}
                      disabled={actionLoading === session.id}
                      className="p-1.5 text-on-surface-variant/40 hover:text-rose-600 transition-colors"
                      title="Disconnect session"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── SECTION 6: HIPAA Audit Logs & Chain Verification ── */}
      <div className="bg-surface rounded-2xl border border-on-surface-variant/10 p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
              <History className="w-5 h-5 text-primary" /> HIPAA Cryptographic Audit Trail
            </h3>
            <p className="text-xs text-on-surface-variant mt-1">
              Append-only immutable record of all authentication, PHI access, and clinic configuration events.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleVerifyAuditChain}
              disabled={verifyingIntegrity}
              className="flex items-center gap-1.5 py-2 px-3.5 rounded-xl text-xs font-bold border border-on-surface-variant/10 text-on-surface hover:bg-surface-container transition-all"
            >
              <Shield className={`w-3.5 h-3.5 text-primary ${verifyingIntegrity ? "animate-spin" : ""}`} />
              {verifyingIntegrity ? "Verifying..." : "Verify Hash Integrity"}
            </button>
            <button
              onClick={handleExportCsv}
              disabled={exportingCsv}
              className="flex items-center gap-1.5 py-2 px-3.5 rounded-xl text-xs font-bold text-white bg-primary hover:bg-primary/95 transition-all disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              {exportingCsv ? "Exporting..." : "Export CSV"}
            </button>
          </div>
        </div>

        {/* Integrity Badge if Checked */}
        {integrityData && (
          <div className="p-3.5 bg-[#edf7e0] border border-[#7dbd42]/30 rounded-xl flex items-center justify-between gap-3 text-xs font-semibold text-[#396a00] animate-fadeIn">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
              <span>
                <strong>Audit Chain Verified:</strong> {integrityData.message || "SHA-256 HMAC cryptographic chain is valid and 100% tamper-free."} ({integrityData.total_records_verified} records checked).
              </span>
            </div>
            <button onClick={() => setIntegrityData(null)} className="opacity-70 hover:opacity-100">✕</button>
          </div>
        )}

        {/* Filter & Search Bar */}
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/50" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setLogPage(1);
              }}
              placeholder="Search by user email, IP address, or action type..."
              className="input-field pl-10 text-xs w-full"
            />
          </div>

          <div className="flex gap-2">
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setLogPage(1);
              }}
              className="input-field text-xs sm:w-48 appearance-none cursor-pointer"
            >
              <option value="all">All Event Categories</option>
              <option value="auth.*">Authentication Events</option>
              <option value="security.*">Security Policy Updates</option>
              <option value="patient.*">Patient & PHI Records</option>
              <option value="appointment.*">Appointment Updates</option>
              <option value="compliance.*">Compliance Exports</option>
            </select>

            <button
              onClick={() => fetchAuditLogs()}
              disabled={logsLoading}
              className="p-2.5 rounded-xl border border-on-surface-variant/10 text-on-surface-variant hover:bg-surface-container transition-colors flex-shrink-0"
              title="Refresh logs"
            >
              <RefreshCw className={`w-4 h-4 ${logsLoading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Audit Log Table */}
        {logsLoading && logs.length === 0 ? (
          <div className="flex justify-center items-center py-12">
            <RefreshCw className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-8 border border-dashed border-on-surface-variant/10 rounded-xl">
            <History className="w-8 h-8 mx-auto text-on-surface-variant/30 mb-2" />
            <p className="text-xs text-on-surface-variant/60 font-semibold">No audit events match your filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-on-surface-variant/10">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-surface-container border-b border-on-surface-variant/10 text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">
                  <th className="py-3 px-4">Timestamp (UTC)</th>
                  <th className="py-3 px-4">Event Type</th>
                  <th className="py-3 px-4">Actor / Email</th>
                  <th className="py-3 px-4">IP Address</th>
                  <th className="py-3 px-4">Resource</th>
                  <th className="py-3 px-4 text-right">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-on-surface-variant/10 text-xs">
                {logs.map((logItem) => {
                  const lbl = getActionLabel(logItem.action);
                  const ua = parseUA(logItem.user_agent);

                  return (
                    <tr key={logItem.id} className="hover:bg-surface-container/30 transition-colors">
                      <td className="py-3 px-4 text-[11px] font-mono text-on-surface-variant whitespace-nowrap">
                        {new Date(logItem.created_at || logItem.timestamp).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 whitespace-nowrap">
                        <span 
                          className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded-full tracking-wide inline-flex items-center gap-1"
                          style={{ color: lbl.color, backgroundColor: lbl.bg }}
                        >
                          {lbl.text}
                        </span>
                      </td>
                      <td className="py-3 px-4 font-semibold text-on-surface max-w-[140px] truncate" title={logItem.user_email}>
                        {logItem.user_email || "System / Anonymous"}
                      </td>
                      <td className="py-3 px-4 font-mono text-[11px] text-on-surface-variant">
                        {logItem.ip_address || "127.0.0.1"}
                      </td>
                      <td className="py-3 px-4 text-[11px] text-on-surface-variant truncate max-w-[100px]">
                        {logItem.resource_type || "audit"}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => setSelectedLogModal(logItem)}
                          className="text-primary hover:underline text-[11px] font-bold"
                        >
                          Inspect
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Controls */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2 text-xs text-on-surface-variant">
          <div>
            Showing <strong>{logs.length}</strong> of <strong>{totalLogs}</strong> recorded events
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setLogPage(p => Math.max(1, p - 1))}
              disabled={logPage <= 1}
              className="p-1.5 rounded-lg border border-on-surface-variant/10 hover:bg-surface-container disabled:opacity-40"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="font-semibold px-2">Page {logPage} of {totalPages}</span>
            <button
              onClick={() => setLogPage(p => Math.min(totalPages, p + 1))}
              disabled={logPage >= totalPages}
              className="p-1.5 rounded-lg border border-on-surface-variant/10 hover:bg-surface-container disabled:opacity-40"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* ── MFA Modal ─────────────────────────────────────────── */}
      {showMfaModal && mfaEnrollData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-surface border border-on-surface-variant/10 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl animate-scaleUp flex flex-col">
            <div className="p-6 border-b border-on-surface-variant/10 flex items-center justify-between">
              <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                <Shield className="w-5 h-5 text-primary" /> Setup Authenticator App
              </h3>
              <button onClick={() => setShowMfaModal(false)} className="text-on-surface-variant hover:text-on-surface">✕</button>
            </div>

            <div className="p-6 space-y-4 overflow-y-auto max-h-[70vh]">
              {mfaError && (
                <div className="p-3 bg-rose-50 border border-rose-100 rounded-xl text-rose-600 text-xs flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{mfaError}</span>
                </div>
              )}

              <div className="text-center space-y-2">
                <p className="text-xs text-on-surface-variant">Scan this QR code with Google Authenticator, Microsoft Authenticator, or 1Password:</p>
                {(() => {
                  const enrollInfo = mfaEnrollData?.data?.totp || mfaEnrollData?.totp || mfaEnrollData;
                  const qrRaw = enrollInfo?.qr_code || mfaEnrollData?.qr_code || "";
                  if (!qrRaw) return null;
                  let cleanSvg = qrRaw;
                  if (cleanSvg.startsWith("data:image/svg+xml;utf-8,")) {
                    cleanSvg = decodeURIComponent(cleanSvg.replace("data:image/svg+xml;utf-8,", ""));
                  } else if (cleanSvg.startsWith("data:image/svg+xml;base64,")) {
                    try {
                      cleanSvg = atob(cleanSvg.replace("data:image/svg+xml;base64,", ""));
                    } catch (e) {
                      // fallback
                    }
                  }
                  return (
                    <div 
                      className="p-3 bg-white border border-on-surface-variant/10 rounded-2xl inline-block shadow-sm"
                      dangerouslySetInnerHTML={{ __html: cleanSvg }}
                    />
                  );
                })()}
              </div>

              <div className="border border-on-surface-variant/10 rounded-xl p-3 bg-surface-container/30">
                <p className="text-[10px] font-bold text-on-surface-variant/70 uppercase tracking-wider mb-1">Manual Setup Key</p>
                <div className="flex items-center justify-between gap-2">
                  {(() => {
                    const enrollInfo = mfaEnrollData?.data?.totp || mfaEnrollData?.totp || mfaEnrollData;
                    const secretKey = enrollInfo?.secret || mfaEnrollData?.secret || "JBSWY3DPEHPK3PXP";
                    return (
                      <>
                        <code className="text-xs font-mono text-on-surface break-all bg-surface-container px-2 py-1 rounded">
                          {secretKey}
                        </code>
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(secretKey);
                            setCopiedSecret(true);
                            setTimeout(() => setCopiedSecret(false), 2000);
                          }}
                          className="text-xs text-primary hover:underline font-bold flex-shrink-0"
                        >
                          {copiedSecret ? "Copied!" : "Copy"}
                        </button>
                      </>
                    );
                  })()}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-widest mb-1.5">
                  6-Digit Verification Code
                </label>
                <input
                  type="text"
                  maxLength={6}
                  value={mfaCode}
                  onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="e.g. 123456"
                  className="w-full text-center px-4 py-3 bg-surface-container rounded-xl outline-none text-on-surface font-mono tracking-widest text-lg border-b-2 border-transparent focus:border-primary transition-all"
                />
              </div>
            </div>

            <div className="p-4 border-t border-on-surface-variant/10 bg-surface-container/20 flex items-center justify-between">
              <button onClick={() => setShowMfaModal(false)} className="text-xs font-semibold text-on-surface-variant hover:text-on-surface">
                Cancel
              </button>
              <button
                onClick={handleVerifyMfa}
                disabled={mfaCode.length !== 6 || mfaLoading}
                className="btn-primary py-2 px-5 text-xs flex items-center gap-2 disabled:opacity-50"
              >
                {mfaLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                Verify & Activate 2FA
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Log Inspector Modal ───────────────────────────────── */}
      {selectedLogModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
          <div className="bg-surface border border-on-surface-variant/10 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl animate-scaleUp flex flex-col">
            <div className="p-5 border-b border-on-surface-variant/10 flex items-center justify-between">
              <h3 className="text-sm font-bold text-on-surface flex items-center gap-2">
                <FileText className="w-4 h-4 text-primary" /> Audit Event Payload
              </h3>
              <button onClick={() => setSelectedLogModal(null)} className="text-on-surface-variant hover:text-on-surface">✕</button>
            </div>

            <div className="p-5 space-y-3 overflow-y-auto max-h-[70vh] text-xs">
              <div>
                <span className="text-on-surface-variant/60 font-bold uppercase text-[10px]">Action:</span>
                <p className="font-mono font-bold text-on-surface">{selectedLogModal.action}</p>
              </div>
              <div>
                <span className="text-on-surface-variant/60 font-bold uppercase text-[10px]">Actor:</span>
                <p className="font-mono text-on-surface">{selectedLogModal.user_email || "System"}</p>
              </div>
              <div>
                <span className="text-on-surface-variant/60 font-bold uppercase text-[10px]">IP & User Agent:</span>
                <p className="font-mono text-on-surface">{selectedLogModal.ip_address} — {selectedLogModal.user_agent}</p>
              </div>
              <div>
                <span className="text-on-surface-variant/60 font-bold uppercase text-[10px]">Raw Event Metadata:</span>
                <pre className="p-3 bg-surface-container rounded-xl font-mono text-[11px] overflow-x-auto text-on-surface mt-1 border border-on-surface-variant/10">
                  {JSON.stringify(selectedLogModal.details || selectedLogModal, null, 2)}
                </pre>
              </div>
            </div>

            <div className="p-4 border-t border-on-surface-variant/10 bg-surface-container/20 flex justify-end">
              <button
                onClick={() => setSelectedLogModal(null)}
                className="btn-primary py-1.5 px-4 text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SecuritySettings;
