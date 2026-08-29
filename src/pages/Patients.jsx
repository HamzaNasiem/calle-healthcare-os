import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Search,
  X,
  Calendar,
  Phone,
  MessageSquare,
  Plus,
  ArrowUpRight,
  CheckCircle2,
  AlertCircle,
  Clock,
  Edit,
  Sparkles,
  Shield,
  Filter,
  Download,
  ChevronRight,
  Eye,
  RefreshCw,
  Copy,
  Check,
  UserCheck
} from "lucide-react";
import api from "../lib/api";
import { format, parseISO, differenceInYears, differenceInDays } from "date-fns";
import { useAuth } from "../context/AuthContext";
import { translations } from "../lib/translations";
import PatientDetailsModal, { getRecallTag } from "../components/PatientDetailsModal";

/* ─── Helpers ─────────────────────────────────────────────── */
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

export default function Patients() {
  const { getCacheItem, setCacheItem, language } = useAuth();
  const t = translations[language] || translations.en;

  // Data states
  const [patients, setPatients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState("All");
  const [meta, setMeta] = useState({ total: 0, page: 1, per_page: 50 });
  const [copiedId, setCopiedId] = useState(null);

  // Selection & Details Drawer state
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  // Modals state
  const [showAddPatientModal, setShowAddPatientModal] = useState(false);
  const [showEditPatientModal, setShowEditPatientModal] = useState(false);
  const [showBookApptModal, setShowBookApptModal] = useState(false);
  const [showMessageModal, setShowMessageModal] = useState(false);
  const [recallToast, setRecallToast] = useState(null);

  // Appointment types for booking
  const [apptTypes, setApptTypes] = useState([
    { name: "Initial Consultation", duration: 60, duration_minutes: 60, fee: 150 },
    { name: "Follow-up Visit", duration: 30, duration_minutes: 30, fee: 75 },
    { name: "Recall Checkup", duration: 45, duration_minutes: 45, fee: 120 }
  ]);

  // Form states
  const [bookForm, setBookForm] = useState({ appointment_type: "Initial Consultation", date: "", time: "", duration_minutes: 60 });
  const [bookSaving, setBookSaving] = useState(false);
  const [bookError, setBookError] = useState("");

  const [msgText, setMsgText] = useState("");
  const [msgSending, setMsgSending] = useState(false);
  const [msgError, setMsgError] = useState("");
  const [msgSent, setMsgSent] = useState(false);

  const [addForm, setAddForm] = useState({
    name: "",
    phone: "",
    email: "",
    date_of_birth: "",
    insurance_provider: "",
    insurance_member_id: "",
    notes: "",
    preferred_time: "morning"
  });
  const [addSaving, setAddSaving] = useState(false);
  const [addError, setAddError] = useState("");

  const [editForm, setEditForm] = useState({
    name: "",
    phone: "",
    email: "",
    date_of_birth: "",
    insurance_provider: "",
    insurance_member_id: "",
    preferred_time: "morning",
    notes: "",
    recall_opted_out: false,
    is_vip: false
  });
  const [editSaving, setEditSaving] = useState(false);
  const [editError, setEditError] = useState("");

  // Load appointment types from clinic settings
  useEffect(() => {
    const info = JSON.parse(localStorage.getItem("clinic-info") || sessionStorage.getItem("clinic-info") || "{}");
    if (info.clinicId) {
      api.get(`/clinics/${info.clinicId}`).then(res => {
        const types = res.data?.data?.appointment_types;
        if (Array.isArray(types) && types.length > 0) {
          setApptTypes(types);
        }
      }).catch(err => console.error("Failed to load appointment types:", err));
    }
  }, []);

  // Fetch Patients List
  const fetchPatients = useCallback(async (searchTerm = "", filterType = "All", bypassCache = false) => {
    const cacheKey = `patients:dir:${filterType}:${searchTerm}`;
    const cached = bypassCache ? null : getCacheItem(cacheKey);
    if (cached) {
      setPatients(cached.patients);
      setMeta(cached.meta);
      setLoading(false);
    } else {
      setLoading(true);
    }

    try {
      // Map filterType to API query parameters
      let recallParam = null;
      if (filterType === "Due for Recall") recallParam = "due_for_recall";
      if (filterType === "Overdue 60d+") recallParam = "overdue_60d";
      if (filterType === "Up to Date") recallParam = "up_to_date";

      // Attempt v1 API, fallback to standard supabase router
      try {
        const params = new URLSearchParams({ page: 1, per_page: 100 });
        if (searchTerm) params.set("search", searchTerm);
        if (recallParam) params.set("recall_status", recallParam);
        if (filterType === "VIP") params.set("is_vip", "true");

        const res = await api.get(`/patients?${params.toString()}`);
        const data = res.data?.data?.patients || res.data?.data || [];
        const metaData = res.data?.meta || { total: data.length, page: 1 };
        
        // Client-side fallback filter if API didn't filter
        let finalData = data;
        if (filterType === "VIP") {
          finalData = finalData.filter(p => p.is_vip);
        } else if (filterType === "Due for Recall") {
          finalData = finalData.filter(p => {
            const tag = getRecallTag(p);
            return tag.label === "Due for Recall" || tag.label === "Overdue 60d+";
          });
        } else if (filterType === "Overdue 60d+") {
          finalData = finalData.filter(p => getRecallTag(p).label === "Overdue 60d+");
        } else if (filterType === "Up to Date") {
          finalData = finalData.filter(p => getRecallTag(p).label === "Up to Date");
        }

        setPatients(finalData);
        setMeta({ ...metaData, total: finalData.length });
        setCacheItem(cacheKey, { patients: finalData, meta: { ...metaData, total: finalData.length } });
      } catch {
        // Fallback supabase endpoint
        const params = new URLSearchParams({ page: 1, limit: 100 });
        if (searchTerm) params.set("search", searchTerm);
        const res = await api.get(`/patients?${params.toString()}`);
        const rawData = res.data?.data || [];
        
        let filtered = rawData;
        if (filterType === "VIP") {
          filtered = filtered.filter(p => p.is_vip);
        } else if (filterType === "Due for Recall") {
          filtered = filtered.filter(p => {
            const tag = getRecallTag(p);
            return tag.label === "Due for Recall" || tag.label === "Overdue 60d+";
          });
        } else if (filterType === "Overdue 60d+") {
          filtered = filtered.filter(p => getRecallTag(p).label === "Overdue 60d+");
        } else if (filterType === "Up to Date") {
          filtered = filtered.filter(p => getRecallTag(p).label === "Up to Date");
        }

        setPatients(filtered);
        setMeta({ total: filtered.length, page: 1 });
        setCacheItem(cacheKey, { patients: filtered, meta: { total: filtered.length, page: 1 } });
      }
    } catch (err) {
      console.error("Failed to fetch patients", err);
    } finally {
      setLoading(false);
    }
  }, [getCacheItem, setCacheItem]);

  // Debounced search trigger
  useEffect(() => {
    const handle = setTimeout(() => {
      fetchPatients(search, activeFilter);
    }, 250);
    return () => clearTimeout(handle);
  }, [search, activeFilter, fetchPatients]);

  // Select patient and fetch deep profile
  const handleSelectPatient = async (p) => {
    setSelectedPatient(p);
    setIsDrawerOpen(true);
    setDetailLoading(true);
    setDetail(null);
    try {
      const res = await api.get(`/patients/${p.id}`);
      setDetail(res.data?.data || res.data);
    } catch (err) {
      console.error("Failed to fetch patient detail", err);
    } finally {
      setDetailLoading(false);
    }
  };

  // Open Edit Modal
  const openEditModal = (p = selectedPatient) => {
    const target = detail?.patient || p;
    if (!target) return;
    setEditForm({
      name: target.name || target.full_name || "",
      phone: target.phone || "",
      email: target.email || "",
      date_of_birth: target.date_of_birth || target.dob || "",
      insurance_provider: target.insurance_provider || "",
      insurance_member_id: target.insurance_member_id || "",
      preferred_time: target.preferred_time || "morning",
      notes: target.notes || "",
      recall_opted_out: target.recall_opted_out || false,
      is_vip: target.is_vip || false
    });
    setEditError("");
    setShowEditPatientModal(true);
  };

  // Handle patient update
  const handleSaveEdit = async () => {
    if (!editForm.name || !editForm.phone) {
      setEditError("Name and phone number are required.");
      return;
    }
    setEditSaving(true);
    setEditError("");
    try {
      const res = await api.put(`/patients/${selectedPatient.id}`, {
        full_name: editForm.name,
        name: editForm.name,
        phone: editForm.phone,
        email: editForm.email,
        dob: editForm.date_of_birth,
        date_of_birth: editForm.date_of_birth,
        insurance_provider: editForm.insurance_provider,
        insurance_member_id: editForm.insurance_member_id,
        preferred_time: editForm.preferred_time,
        notes: editForm.notes,
        recall_opted_out: editForm.recall_opted_out,
        is_vip: editForm.is_vip
      });

      const updated = res.data?.data || res.data;
      setSelectedPatient(prev => ({ ...prev, ...updated }));
      if (detail) {
        setDetail(prev => ({ ...prev, patient: { ...(prev?.patient || {}), ...updated } }));
      }

      fetchPatients(search, activeFilter, true);
      setShowEditPatientModal(false);
    } catch (err) {
      setEditError(err.response?.data?.detail || err.response?.data?.error || "Failed to update profile.");
    } finally {
      setEditSaving(false);
    }
  };

  // Quick Trigger Recall Call via CALL-E
  const handleQuickRecall = async (p, e) => {
    if (e) e.stopPropagation();
    if (p.recall_opted_out) {
      alert("This patient has opted out of automated recall calls.");
      return;
    }
    try {
      let res;
      try {
        res = await api.post(`/patients/${p.id}/trigger-recall`);
      } catch {
        res = await api.post(`/patients/recall/${p.id}`);
      }
      setRecallToast({ name: p.name || p.full_name, success: true });
      setTimeout(() => setRecallToast(null), 4000);
    } catch (err) {
      alert("Failed to initiate recall call: " + (err.response?.data?.detail || err.message));
    }
  };

  // Copy phone / text helper
  const copyText = (text, id, e) => {
    if (e) e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  const getAge = (dobString) => {
    if (!dobString) return null;
    try {
      return differenceInYears(new Date(), parseISO(dobString));
    } catch {
      return null;
    }
  };

  const [exporting, setExporting] = useState(false);

  const handleExportCSV = async () => {
    try {
      setExporting(true);
      const res = await api.get("/patients/export", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `patients_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("[Patients.handleExportCSV] Error:", err);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-12 min-h-screen">
      
      {/* ── Page Header & Stats Bar ────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-on-surface tracking-tight flex items-center gap-2.5">
            Patients & EHR Directory
            <span className="text-xs font-mono font-medium px-2.5 py-0.5 rounded-full bg-primary/10 text-primary border border-primary/20">
              AES-256 Encrypted
            </span>
          </h1>
          <p className="text-xs text-on-surface-variant mt-1">
            HIPAA-compliant Master Patient Index with real-time CALL-E Voice AI recall dispatch.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <button
            onClick={handleExportCSV}
            disabled={exporting}
            className="btn-secondary text-xs py-2 px-3.5 flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <Download className="w-3.5 h-3.5" />
            {exporting ? "Exporting..." : "Export CSV"}
          </button>
          <button
            onClick={() => setShowAddPatientModal(true)}
            className="btn-primary text-xs py-2 px-4 flex items-center gap-1.5 shadow-sm cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            Add Patient
          </button>
        </div>
      </div>

      {/* ── Toast Notification ─────────────────────────────────────────────── */}
      {recallToast && (
        <div className="p-3.5 bg-emerald-500/15 border border-emerald-500/30 text-emerald-800 dark:text-emerald-300 rounded-xl text-xs flex items-center justify-between shadow-sm animate-in fade-in slide-in-from-top duration-200">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-emerald-600 animate-spin" />
            <span>
              <strong>CALL-E Voice AI dispatched:</strong> Outbound recall call initiated for <strong>{recallToast.name}</strong>.
            </span>
          </div>
          <button onClick={() => setRecallToast(null)} className="p-1 hover:opacity-70">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* ── Filter Bar & Instant Search ─────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 bg-surface-container-lowest p-3 rounded-2xl border border-surface-container shadow-xs">
        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto thin-scrollbar pb-1 md:pb-0">
          {[
            { id: "All", label: "All Patients" },
            { id: "Due for Recall", label: "Due for Recall" },
            { id: "Overdue 60d+", label: "Overdue 60d+" },
            { id: "Up to Date", label: "Up to Date" },
            { id: "VIP", label: "VIP Only" },
          ].map((tab) => {
            const isActive = activeFilter === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveFilter(tab.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  isActive
                    ? "bg-primary text-white shadow-xs"
                    : "bg-surface-container/60 text-on-surface-variant hover:text-on-surface hover:bg-surface-container"
                }`}
              >
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Instant Search Box */}
        <div className="relative w-full md:w-80 flex-shrink-0">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/50" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, phone, or member ID..."
            className="w-full pl-9 pr-8 py-2 bg-surface-container rounded-xl text-xs outline-none text-on-surface placeholder-on-surface-variant/50 focus:ring-1 focus:ring-primary border border-transparent focus:border-primary transition-all"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-on-surface-variant hover:text-on-surface"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* ── Patient Master Table ───────────────────────────────────────────── */}
      <div className="bg-surface-container-lowest rounded-2xl border border-surface-container shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-surface-container bg-surface-container/30 text-[0.7rem] uppercase tracking-wider font-bold text-on-surface-variant">
                <th className="py-3.5 px-4 sm:px-6">Patient Name</th>
                <th className="py-3.5 px-4">DOB / Age</th>
                <th className="py-3.5 px-4">Phone Number</th>
                <th className="py-3.5 px-4">Insurance Provider</th>
                <th className="py-3.5 px-4">Last Visit</th>
                <th className="py-3.5 px-4">Recall Status</th>
                <th className="py-3.5 px-4 sm:px-6 text-right">Quick Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container text-xs">
              {loading ? (
                [...Array(6)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-surface-container flex-shrink-0" />
                        <div className="space-y-1.5">
                          <div className="w-32 h-3.5 bg-surface-container rounded" />
                          <div className="w-20 h-2.5 bg-surface-container rounded" />
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-4"><div className="w-24 h-3 bg-surface-container rounded" /></td>
                    <td className="py-4 px-4"><div className="w-28 h-3 bg-surface-container rounded" /></td>
                    <td className="py-4 px-4"><div className="w-24 h-3 bg-surface-container rounded" /></td>
                    <td className="py-4 px-4"><div className="w-20 h-3 bg-surface-container rounded" /></td>
                    <td className="py-4 px-4"><div className="w-24 h-6 bg-surface-container rounded-full" /></td>
                    <td className="py-4 px-6 text-right"><div className="w-16 h-7 bg-surface-container rounded-lg ml-auto" /></td>
                  </tr>
                ))
              ) : patients.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-on-surface-variant">
                    <UserCheck className="w-10 h-10 mx-auto text-on-surface-variant/30 mb-2" />
                    <p className="font-semibold text-on-surface text-sm">No matching patients found</p>
                    <p className="text-xs text-on-surface-variant mt-1">Try adjusting your search query or filter pills.</p>
                  </td>
                </tr>
              ) : (
                patients.map((p) => {
                  const patName = p.name || p.full_name || "Unknown";
                  const patPhone = p.phone || "—";
                  const patDob = p.date_of_birth || p.dob;
                  const age = p.age ?? getAge(patDob);
                  const recallTag = getRecallTag(p);
                  const RecallIcon = recallTag.icon;
                  const style = avatarStyle(patName);

                  return (
                    <tr
                      key={p.id}
                      onClick={() => handleSelectPatient(p)}
                      className="hover:bg-surface-container/50 transition-colors cursor-pointer group"
                    >
                      {/* 1. Name & Avatar */}
                      <td className="py-3.5 px-4 sm:px-6">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-9 h-9 rounded-full flex items-center justify-center font-bold text-xs flex-shrink-0 shadow-xs"
                            style={{ backgroundColor: style.bg, color: style.text }}
                          >
                            {initials(patName)}
                          </div>
                          <div className="min-w-0">
                            <div className="flex items-center gap-1.5">
                              <span className="font-semibold text-on-surface text-sm group-hover:text-primary transition-colors truncate">
                                {patName}
                              </span>
                              {p.is_vip && (
                                <span className="px-1.5 py-0.2 text-[0.6rem] font-bold bg-amber-500/15 text-amber-600 rounded-md border border-amber-500/30">
                                  VIP
                                </span>
                              )}
                            </div>
                            <p className="text-[0.7rem] text-on-surface-variant font-mono">
                              ID: {p.id.slice(0, 8)}...
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* 2. DOB / Age */}
                      <td className="py-3.5 px-4 text-on-surface-variant">
                        {patDob ? (
                          <div>
                            <span className="text-on-surface font-medium block">
                              {format(parseISO(patDob), "MMM d, yyyy")}
                            </span>
                            <span className="text-[0.7rem] text-on-surface-variant">
                              {age !== null ? `${age} yrs` : "—"}
                            </span>
                          </div>
                        ) : (
                          <span className="text-on-surface-variant/60">—</span>
                        )}
                      </td>

                      {/* 3. Phone */}
                      <td className="py-3.5 px-4 font-mono text-on-surface">
                        <div className="flex items-center gap-1.5">
                          <span>{patPhone}</span>
                          <button
                            onClick={(e) => copyText(patPhone, `phone-${p.id}`, e)}
                            className="text-on-surface-variant hover:text-primary p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                            title="Copy phone"
                          >
                            {copiedId === `phone-${p.id}` ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                          </button>
                        </div>
                      </td>

                      {/* 4. Insurance */}
                      <td className="py-3.5 px-4">
                        <div className="min-w-0 max-w-[140px]">
                          <span className="font-medium text-on-surface truncate block">
                            {p.insurance_provider || "Self-Pay"}
                          </span>
                          {p.insurance_member_id && (
                            <span className="text-[0.65rem] text-on-surface-variant font-mono truncate block">
                              #{p.insurance_member_id}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* 5. Last Visit */}
                      <td className="py-3.5 px-4 text-on-surface-variant">
                        {p.last_visit_date ? (
                          <div>
                            <span className="text-on-surface font-medium block">
                              {format(parseISO(p.last_visit_date), "MMM d, yyyy")}
                            </span>
                            <span className="text-[0.65rem] text-on-surface-variant">
                              {differenceInDays(new Date(), parseISO(p.last_visit_date))}d ago
                            </span>
                          </div>
                        ) : (
                          <span className="text-amber-600 font-medium">New Patient</span>
                        )}
                      </td>

                      {/* 6. Recall Status Tag */}
                      <td className="py-3.5 px-4">
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${recallTag.bg} ${recallTag.border}`}>
                          {RecallIcon && <RecallIcon className="w-3.5 h-3.5" />}
                          {recallTag.label}
                        </span>
                      </td>

                      {/* 7. Action Buttons */}
                      <td className="py-3.5 px-4 sm:px-6 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {!p.recall_opted_out && recallTag.label !== "Up to Date" && (
                            <button
                              onClick={(e) => handleQuickRecall(p, e)}
                              className="px-2.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold flex items-center gap-1 shadow-xs transition-colors"
                              title="Trigger CALL-E Voice Recall Call"
                            >
                              <Phone className="w-3 h-3" />
                              Recall
                            </button>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSelectPatient(p);
                            }}
                            className="px-2.5 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface text-xs font-semibold flex items-center gap-1 transition-colors"
                          >
                            View
                            <ChevronRight className="w-3 h-3" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Table Footer */}
        <div className="p-4 bg-surface-container/20 border-t border-surface-container flex items-center justify-between text-xs text-on-surface-variant">
          <span>Showing {patients.length} of {meta.total} registered patients</span>
          <span className="font-mono text-[0.7rem]">HIPAA Safe Harbour Compliant · AES-256 Encrypted</span>
        </div>
      </div>

      {/* ── Integrated Patient Details Modal / Drawer ───────────────────────── */}
      <PatientDetailsModal
        patient={selectedPatient}
        detail={detail}
        loading={detailLoading}
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        onBook={() => setShowBookApptModal(true)}
        onMessage={() => {
          setShowMessageModal(true);
          setMsgText("");
          setMsgError("");
          setMsgSent(false);
        }}
        onEdit={() => openEditModal(selectedPatient)}
        onRecallTriggered={(patId) => {
          setRecallToast({ name: selectedPatient?.name || selectedPatient?.full_name, success: true });
          setTimeout(() => setRecallToast(null), 4000);
        }}
      />

      {/* ── MODAL 1: Add New Patient ────────────────────────────────────────── */}
      {showAddPatientModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-surface-container-lowest border border-surface-container rounded-2xl w-full max-w-lg p-6 shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-surface-container pb-4 mb-4">
              <div>
                <h2 className="text-lg font-bold text-on-surface">Add New Patient</h2>
                <p className="text-xs text-on-surface-variant">Register clinical and demographic profile with AES-256 encryption.</p>
              </div>
              <button onClick={() => setShowAddPatientModal(false)} className="p-1.5 text-on-surface-variant hover:bg-surface-container rounded-full">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="overline mb-1 block">Full Name *</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface border border-transparent focus:border-primary"
                    placeholder="e.g. Eleanor Vance"
                    value={addForm.name}
                    onChange={(e) => setAddForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="overline mb-1 block">Phone Number *</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface border border-transparent focus:border-primary"
                    placeholder="+1 (555) 000-0000"
                    value={addForm.phone}
                    onChange={(e) => setAddForm((f) => ({ ...f, phone: e.target.value }))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="overline mb-1 block">Email (optional)</label>
                  <input
                    type="email"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface border border-transparent focus:border-primary"
                    placeholder="patient@example.com"
                    value={addForm.email}
                    onChange={(e) => setAddForm((f) => ({ ...f, email: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="overline mb-1 block">Date of Birth</label>
                  <input
                    type="date"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface border border-transparent focus:border-primary"
                    value={addForm.date_of_birth}
                    onChange={(e) => setAddForm((f) => ({ ...f, date_of_birth: e.target.value }))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="overline mb-1 block">Insurance Provider</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface border border-transparent focus:border-primary"
                    placeholder="e.g. Aetna, Blue Cross"
                    value={addForm.insurance_provider}
                    onChange={(e) => setAddForm((f) => ({ ...f, insurance_provider: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="overline mb-1 block">Member ID</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface border border-transparent focus:border-primary"
                    placeholder="e.g. ID-894210"
                    value={addForm.insurance_member_id}
                    onChange={(e) => setAddForm((f) => ({ ...f, insurance_member_id: e.target.value }))}
                  />
                </div>
              </div>
            </div>

            {addError && <p className="text-xs text-red-600 mt-3 font-semibold">{addError}</p>}

            <div className="flex justify-end gap-2.5 mt-6 border-t border-surface-container pt-4">
              <button
                onClick={() => setShowAddPatientModal(false)}
                className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={addSaving}
                onClick={async () => {
                  setAddError("");
                  if (!addForm.name || !addForm.phone) {
                    setAddError("Name and Phone are required.");
                    return;
                  }
                  setAddSaving(true);
                  try {
                    await api.post("/patients", {
                      full_name: addForm.name,
                      name: addForm.name,
                      phone: addForm.phone,
                      email: addForm.email,
                      dob: addForm.date_of_birth,
                      date_of_birth: addForm.date_of_birth,
                      insurance_provider: addForm.insurance_provider,
                      insurance_member_id: addForm.insurance_member_id,
                      preferred_time: addForm.preferred_time
                    });
                    fetchPatients("", "All", true);
                    setShowAddPatientModal(false);
                    setAddForm({ name: "", phone: "", email: "", date_of_birth: "", insurance_provider: "", insurance_member_id: "", notes: "", preferred_time: "morning" });
                  } catch (err) {
                    setAddError(err.response?.data?.detail || err.response?.data?.error || "Failed to create patient.");
                  } finally {
                    setAddSaving(false);
                  }
                }}
                className="btn-primary text-xs px-5 py-2 disabled:opacity-50"
              >
                {addSaving ? "Saving..." : "Save Patient"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL 2: Edit Patient Profile ───────────────────────────────────── */}
      {showEditPatientModal && selectedPatient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-surface-container-lowest border border-surface-container rounded-2xl w-full max-w-lg p-6 shadow-2xl animate-in zoom-in-95 duration-200 overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between border-b border-surface-container pb-4 mb-4">
              <div>
                <h2 className="text-lg font-bold text-on-surface">Edit Patient Record</h2>
                <p className="text-xs text-on-surface-variant">Update encrypted demographics, recall preferences, and notes.</p>
              </div>
              <button onClick={() => setShowEditPatientModal(false)} className="p-1.5 text-on-surface-variant hover:bg-surface-container rounded-full">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="overline mb-1 block">Full Name *</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={editForm.name}
                    onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="overline mb-1 block">Phone Number *</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={editForm.phone}
                    onChange={(e) => setEditForm((f) => ({ ...f, phone: e.target.value }))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="overline mb-1 block">Email</label>
                  <input
                    type="email"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={editForm.email}
                    onChange={(e) => setEditForm((f) => ({ ...f, email: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="overline mb-1 block">Date of Birth</label>
                  <input
                    type="date"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={editForm.date_of_birth}
                    onChange={(e) => setEditForm((f) => ({ ...f, date_of_birth: e.target.value }))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="overline mb-1 block">Insurance Provider</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={editForm.insurance_provider}
                    onChange={(e) => setEditForm((f) => ({ ...f, insurance_provider: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="overline mb-1 block">Member ID</label>
                  <input
                    type="text"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={editForm.insurance_member_id}
                    onChange={(e) => setEditForm((f) => ({ ...f, insurance_member_id: e.target.value }))}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                <div>
                  <label className="overline mb-1 block">Preferred Recall Time</label>
                  <select
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={editForm.preferred_time}
                    onChange={(e) => setEditForm((f) => ({ ...f, preferred_time: e.target.value }))}
                  >
                    <option value="morning">Morning (8am - 12pm)</option>
                    <option value="afternoon">Afternoon (12pm - 5pm)</option>
                    <option value="evening">Evening (5pm - 8pm)</option>
                  </select>
                </div>

                <div className="flex flex-col justify-end gap-2">
                  <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-on-surface">
                    <input
                      type="checkbox"
                      checked={editForm.recall_opted_out}
                      onChange={(e) => setEditForm((f) => ({ ...f, recall_opted_out: e.target.checked }))}
                      className="rounded border-surface-container text-primary w-4 h-4"
                    />
                    <span>Opt-out of Auto-Recall Calls</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-on-surface">
                    <input
                      type="checkbox"
                      checked={editForm.is_vip}
                      onChange={(e) => setEditForm((f) => ({ ...f, is_vip: e.target.checked }))}
                      className="rounded border-surface-container text-primary w-4 h-4"
                    />
                    <span>VIP Patient Status</span>
                  </label>
                </div>
              </div>

              <div>
                <label className="overline mb-1 block">Clinical Notes & Comments</label>
                <textarea
                  className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface resize-none h-20"
                  placeholder="Add confidential clinical observations or special instructions..."
                  value={editForm.notes}
                  onChange={(e) => setEditForm((f) => ({ ...f, notes: e.target.value }))}
                />
              </div>
            </div>

            {editError && <p className="text-xs text-red-600 mt-3 font-semibold">{editError}</p>}

            <div className="flex justify-end gap-2.5 mt-6 border-t border-surface-container pt-4">
              <button
                onClick={() => setShowEditPatientModal(false)}
                className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={editSaving}
                onClick={handleSaveEdit}
                className="btn-primary text-xs px-5 py-2 disabled:opacity-50"
              >
                {editSaving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL 3: Book Appointment ───────────────────────────────────────── */}
      {showBookApptModal && selectedPatient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-surface-container-lowest border border-surface-container rounded-2xl w-full max-w-md p-6 shadow-2xl animate-in zoom-in-95 duration-200">
            <h2 className="text-lg font-bold text-on-surface mb-1">Schedule Visit</h2>
            <p className="text-xs text-on-surface-variant mb-4">
              Booking for: <strong>{selectedPatient.name || selectedPatient.full_name}</strong>
            </p>

            <div className="space-y-3">
              <div>
                <label className="overline mb-1 block">Service Type</label>
                <select
                  className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                  value={bookForm.appointment_type}
                  onChange={(e) => setBookForm((f) => ({ ...f, appointment_type: e.target.value }))}
                >
                  {apptTypes.map((t, idx) => (
                    <option key={idx} value={t.name}>
                      {t.name} ({t.duration_minutes || t.duration || 30} min · ${t.fee || 100})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="overline mb-1 block">Date *</label>
                  <input
                    type="date"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={bookForm.date}
                    onChange={(e) => setBookForm((f) => ({ ...f, date: e.target.value }))}
                  />
                </div>
                <div>
                  <label className="overline mb-1 block">Time *</label>
                  <input
                    type="time"
                    className="w-full bg-surface-container rounded-xl px-3.5 py-2 text-xs outline-none text-on-surface"
                    value={bookForm.time}
                    onChange={(e) => setBookForm((f) => ({ ...f, time: e.target.value }))}
                  />
                </div>
              </div>
            </div>

            {bookError && <p className="text-xs text-red-600 mt-3">{bookError}</p>}

            <div className="flex justify-end gap-2.5 mt-6 border-t border-surface-container pt-4">
              <button
                onClick={() => setShowBookApptModal(false)}
                className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-xl transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={bookSaving}
                onClick={async () => {
                  setBookError("");
                  if (!bookForm.date || !bookForm.time) {
                    setBookError("Date and Time are required.");
                    return;
                  }
                  setBookSaving(true);
                  try {
                    const datetime = new Date(`${bookForm.date}T${bookForm.time}:00`).toISOString();
                    await api.post("/appointments", {
                      patient_id: selectedPatient.id,
                      patient_name: selectedPatient.name || selectedPatient.full_name,
                      patient_phone: selectedPatient.phone,
                      appointment_type: bookForm.appointment_type,
                      datetime,
                      duration_minutes: Number(bookForm.duration_minutes || 60),
                    });
                    fetchPatients(search, activeFilter, true);
                    setShowBookApptModal(false);
                  } catch (err) {
                    setBookError(err.response?.data?.detail || err.response?.data?.error || "Failed to book appointment.");
                  } finally {
                    setBookSaving(false);
                  }
                }}
                className="btn-primary text-xs px-5 py-2 disabled:opacity-50"
              >
                {bookSaving ? "Booking..." : "Confirm Booking"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL 4: Send SMS Link ──────────────────────────────────────────── */}
      {showMessageModal && selectedPatient && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-surface-container-lowest border border-surface-container rounded-2xl w-full max-w-md p-6 shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between border-b border-surface-container pb-3 mb-3">
              <div>
                <h2 className="text-lg font-bold text-on-surface">Send SMS Link</h2>
                <p className="text-xs text-on-surface-variant">To: {selectedPatient.name || selectedPatient.full_name} ({selectedPatient.phone})</p>
              </div>
              <button onClick={() => setShowMessageModal(false)} className="p-1.5 text-on-surface-variant hover:bg-surface-container rounded-full">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              {/* Quick Template Buttons */}
              <div className="flex items-center gap-1.5 flex-wrap">
                <button
                  type="button"
                  onClick={() => setMsgText(`Hi ${selectedPatient.name || selectedPatient.full_name}, this is your clinic. You are due for your routine wellness visit. Schedule online: https://clinic.bytelytic.com/book`)}
                  className="px-2.5 py-1 bg-surface-container hover:bg-surface-container-high text-[0.7rem] rounded-lg text-on-surface"
                >
                  Recall Reminder
                </button>
                <button
                  type="button"
                  onClick={() => setMsgText(`Hi ${selectedPatient.name || selectedPatient.full_name}, please confirm your upcoming clinic appointment by replying YES.`)}
                  className="px-2.5 py-1 bg-surface-container hover:bg-surface-container-high text-[0.7rem] rounded-lg text-on-surface"
                >
                  Appointment Confirmation
                </button>
              </div>

              <textarea
                className="w-full bg-surface-container rounded-xl p-3 text-xs outline-none text-on-surface resize-none h-28 border border-transparent focus:border-primary"
                placeholder="Type your message or booking link here..."
                value={msgText}
                onChange={(e) => { setMsgText(e.target.value); setMsgSent(false); }}
              />

              {msgSent && <p className="text-xs text-emerald-600 font-semibold">✅ SMS dispatched successfully via Twilio/Telnyx.</p>}
              {msgError && <p className="text-xs text-red-600 font-semibold">{msgError}</p>}
            </div>

            <div className="flex justify-end gap-2.5 mt-4 border-t border-surface-container pt-3">
              <button
                onClick={() => setShowMessageModal(false)}
                className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-xl transition-colors"
              >
                Close
              </button>
              <button
                disabled={msgSending || !msgText.trim()}
                onClick={async () => {
                  setMsgSending(true);
                  setMsgError("");
                  setMsgSent(false);
                  try {
                    let res;
                    try {
                      res = await api.post(`/patients/${selectedPatient.id}/message`, { message: msgText.trim() });
                    } catch {
                      res = await api.post(`/patients/${selectedPatient.id}/message`, { message: msgText.trim() });
                    }
                    setMsgSent(true);
                    setMsgText("");
                  } catch (err) {
                    setMsgError(err.response?.data?.detail || err.response?.data?.error || "Failed to send SMS.");
                  } finally {
                    setMsgSending(false);
                  }
                }}
                className="btn-primary text-xs px-5 py-2 disabled:opacity-50"
              >
                {msgSending ? "Sending..." : "Send SMS"}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
