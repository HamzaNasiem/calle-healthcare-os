import React, { useEffect, useState, useCallback } from "react";
import {
  Bot,
  Bell,
  Calendar,
  CheckCircle,
  AlertCircle,
  Loader2,
  Copy,
  ExternalLink,
  Phone,
  MapPin,
  Mail,
  Save,
  Shield,
  Wifi,
  Database,
  AlertTriangle,
  User,
  Users,
  Clock,
  Briefcase,
  DollarSign,
  Plus,
  Trash2,
  Sliders,
  Edit2,
  CreditCard,
  Sparkles,
  Share2,
  Gift,
  Building,
  RefreshCw,
  Zap,
  Check,
  CheckCircle2,
  XCircle,
  Unlink,
  MessageSquare,
  Award,
  ShieldCheck,
  FileText,
  Info,
  Volume2,
  VolumeX,
  Smartphone,
  ShieldAlert,
  Key,
  Webhook,
  Send,
  Lock,
  Eye,
  EyeOff,
  Layers,
  Globe,
  Download,
  FileSpreadsheet,
  FileJson,
  UserX,
  AlertOctagon,
  Archive,
  Hash
} from "lucide-react";
import api from "../lib/api";
import SecuritySettings from "../components/SecuritySettings";
import TeamSettings from "../components/TeamSettings";
import EhrSettings from "../components/EhrSettings";
import AgentBuilderSettings from "../components/AgentBuilderSettings";
import NotificationSettings from "../components/NotificationSettings";
import { DEFAULT_NOTIFICATIONS_CONFIG } from "../components/notificationConstants.js";

import { useAuth } from "../context/AuthContext";
import { translations } from "../lib/translations";

const CREDENTIAL_PRESETS = [
  "MD",
  "DO",
  "PT",
  "DPT",
  "DC",
  "DDS",
  "DMD",
  "PA-C",
  "FNP-C",
  "NP",
  "PsyD",
  "PhD",
  "MS",
  "OTD"
];

const US_TIMEZONES = [
  { value: "America/New_York", label: "Eastern Time (ET) — America/New_York" },
  { value: "America/Chicago", label: "Central Time (CT) — America/Chicago" },
  { value: "America/Denver", label: "Mountain Time (MT) — America/Denver" },
  { value: "America/Phoenix", label: "Arizona (MST, No DST) — America/Phoenix" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT) — America/Los_Angeles" },
  { value: "America/Anchorage", label: "Alaska Time (AKT) — America/Anchorage" },
  { value: "Pacific/Honolulu", label: "Hawaii-Aleutian Time (HST) — Pacific/Honolulu" },
  { value: "America/Puerto_Rico", label: "Atlantic Time (AST) — America/Puerto_Rico" },
  { value: "Europe/London", label: "GMT / British Summer Time — Europe/London" },
  { value: "UTC", label: "Coordinated Universal Time (UTC)" }
];

const SPECIALTIES = [
  "Physical Therapy",
  "Mental Health & Psychology",
  "Chiropractic Care",
  "General Medicine / Family Practice",
  "Dental Clinic & Orthodontics",
  "Pediatric Care",
  "Orthopedics & Sports Medicine",
  "Dermatology",
  "Cardiology",
  "Ophthalmology & Optometry",
  "Neurology",
  "Urgent Care Clinic",
  "Podiatry",
  "Integrative & Functional Medicine",
  "Acupuncture & Holistic Health",
  "Other"
];

const DEFAULT_HOURS = {
  mon: { enabled: true, start: "08:00", end: "18:00" },
  tue: { enabled: true, start: "08:00", end: "18:00" },
  wed: { enabled: true, start: "08:00", end: "18:00" },
  thu: { enabled: true, start: "08:00", end: "18:00" },
  fri: { enabled: true, start: "08:00", end: "18:00" },
  sat: { enabled: false, start: "08:00", end: "18:00" },
  sun: { enabled: false, start: "08:00", end: "18:00" }
};

const DAYS_CONFIG = [
  { key: "mon", label: "Monday" },
  { key: "tue", label: "Tuesday" },
  { key: "wed", label: "Wednesday" },
  { key: "thu", label: "Thursday" },
  { key: "fri", label: "Friday" },
  { key: "sat", label: "Saturday" },
  { key: "sun", label: "Sunday" }
];

const formatTimeLabel = (timeStr) => {
  if (!timeStr) return "";
  const [hStr, mStr] = timeStr.split(":");
  let hour = parseInt(hStr, 10);
  const min = mStr || "00";
  if (isNaN(hour)) return timeStr;
  const ampm = hour >= 12 ? "PM" : "AM";
  const displayHour = hour % 12 === 0 ? 12 : hour % 12;
  return `${displayHour}:${min} ${ampm}`;
};

const BASE_TIME_OPTIONS = (() => {
  const options = [];
  for (let h = 0; h < 24; h++) {
    for (let m = 0; m < 60; m += 30) {
      const val = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
      options.push({ value: val, label: `${val} (${formatTimeLabel(val)})` });
    }
  }
  return options;
})();

const getTimeOptions = (currentVal) => {
  if (!currentVal) return BASE_TIME_OPTIONS;
  const exists = BASE_TIME_OPTIONS.some(opt => opt.value === currentVal);
  if (!exists) {
    const customOpt = { value: currentVal, label: `${currentVal} (${formatTimeLabel(currentVal)})` };
    const all = [...BASE_TIME_OPTIONS, customOpt];
    all.sort((a, b) => a.value.localeCompare(b.value));
    return all;
  }
  return BASE_TIME_OPTIONS;
};

const parseBusinessHoursData = (rawHours) => {
  if (!rawHours) return { ...DEFAULT_HOURS };
  
  let hoursObj = rawHours;
  if (typeof rawHours === "string") {
    try {
      hoursObj = JSON.parse(rawHours);
    } catch {
      return { ...DEFAULT_HOURS };
    }
  }
  if (!hoursObj || typeof hoursObj !== "object") {
    return { ...DEFAULT_HOURS };
  }

  const dayAliases = {
    mon: ["mon", "monday"],
    tue: ["tue", "tues", "tuesday"],
    wed: ["wed", "wednesday"],
    thu: ["thu", "thur", "thurs", "thursday"],
    fri: ["fri", "friday"],
    sat: ["sat", "saturday"],
    sun: ["sun", "sunday"]
  };

  const parsed = {};
  for (const day of ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]) {
    let val = null;
    for (const alias of dayAliases[day]) {
      if (hoursObj[alias] !== undefined) {
        val = hoursObj[alias];
        break;
      }
      const foundKey = Object.keys(hoursObj).find(k => k.toLowerCase() === alias);
      if (foundKey) {
        val = hoursObj[foundKey];
        break;
      }
    }

    if (val === null || val === undefined) {
      parsed[day] = { ...DEFAULT_HOURS[day] };
    } else if (typeof val === "object") {
      const isClosed = val.closed === true || val.enabled === false || val.open === false;
      parsed[day] = {
        enabled: !isClosed,
        start: String(val.start || "08:00").trim(),
        end: String(val.end || "18:00").trim()
      };
    } else if (typeof val === "string") {
      const trimmed = val.trim().toLowerCase();
      if (trimmed === "closed" || trimmed === "" || trimmed === "off") {
        parsed[day] = { enabled: false, start: "08:00", end: "18:00" };
      } else if (trimmed.includes("-") || trimmed.includes("–")) {
        const parts = trimmed.replace("–", "-").split("-").map(s => s.trim());
        parsed[day] = {
          enabled: true,
          start: parts[0] || "08:00",
          end: parts[1] || "18:00"
        };
      } else {
        parsed[day] = { enabled: false, start: "08:00", end: "18:00" };
      }
    } else {
      parsed[day] = { ...DEFAULT_HOURS[day] };
    }
  }
  return parsed;
};

const formatBusinessHoursForDb = (hoursState) => {
  const dbHours = {};
  for (const day of ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]) {
    const d = hoursState[day] || DEFAULT_HOURS[day];
    dbHours[day] = d.enabled ? `${d.start}-${d.end}` : "closed";
  }
  return dbHours;
};


const Settings = () => {
  const { role, language } = useAuth();
  const t = translations[language] || translations.en;
  const isOwner = role === 'owner';
  const [activeTab, setActiveTab] = useState("profile");
  const [clinic, setClinic] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState(null);

  // Notification Preferences State
  const [notifConfig, setNotifConfig] = useState(DEFAULT_NOTIFICATIONS_CONFIG);
  const [savingNotifs, setSavingNotifs] = useState(false);
  const [testingAudio, setTestingAudio] = useState(false);

  // Profile fields — initialized empty until real clinic data is fetched from DB
  const [name, setName] = useState("");
  const [specialty, setSpecialty] = useState("General Practice");
  const [address, setAddress] = useState("");
  const [suite, setSuite] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [timezone, setTimezone] = useState("America/Chicago");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [emergencyProtocols, setEmergencyProtocols] = useState("If caller reports chest pain, severe shortness of breath, sudden numbness, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest emergency department.");
  const [transferPhoneNumber, setTransferPhoneNumber] = useState("");
  const [profileErrors, setProfileErrors] = useState({});
  const [isCustomSpecialty, setIsCustomSpecialty] = useState(false);


  // Doctor fields
  const [doctorName, setDoctorName] = useState("");
  const [doctorCredentials, setDoctorCredentials] = useState("");
  const [doctorPhone, setDoctorPhone] = useState("");
  const [npiNumber, setNpiNumber] = useState("");
  const [medicalLicense, setMedicalLicense] = useState("");
  const [doctorErrors, setDoctorErrors] = useState({});

  const toggleCredential = (cred) => {
    const existing = doctorCredentials
      ? doctorCredentials.split(",").map(c => c.trim()).filter(Boolean)
      : [];
    let updated;
    if (existing.includes(cred)) {
      updated = existing.filter(c => c !== cred);
    } else {
      updated = [...existing, cred];
    }
    setDoctorCredentials(updated.join(", "));
    if (doctorErrors.doctorCredentials) {
      setDoctorErrors(prev => ({ ...prev, doctorCredentials: null }));
    }
  };

  const handleNpiChange = (val) => {
    const digits = val.replace(/\D/g, "").slice(0, 10);
    setNpiNumber(digits);
    if (doctorErrors.npiNumber) {
      setDoctorErrors(prev => ({ ...prev, npiNumber: null }));
    }
  };

  const handleLicenseChange = (val) => {
    setMedicalLicense(val.toUpperCase());
    if (doctorErrors.medicalLicense) {
      setDoctorErrors(prev => ({ ...prev, medicalLicense: null }));
    }
  };

  // Business Hours state
  const [hours, setHours] = useState(DEFAULT_HOURS);

  // Appointment types state
  const [apptTypes, setApptTypes] = useState([]);
  const [newTypeName, setNewTypeName] = useState("");
  const [newTypeDuration, setNewTypeDuration] = useState(30);
  const [newTypeFee, setNewTypeFee] = useState(100);
  const [editingApptIdx, setEditingApptIdx] = useState(null);
  const [editingAppt, setEditingAppt] = useState(null);

  // Integrations state
  const [telnyxNumber, setTelnyxNumber] = useState("");
  const [twilioNumber, setTwilioNumber] = useState("");
  const [googleCalendarId, setGoogleCalendarId] = useState("primary");
  const [integrationsStatus, setIntegrationsStatus] = useState(null);
  const [loadingIntegrations, setLoadingIntegrations] = useState(false);
  const [testingService, setTestingService] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [disconnectingGoogle, setDisconnectingGoogle] = useState(false);
  const [syncingCalle, setSyncingCalle] = useState(false);
  const [openingPortal, setOpeningPortal] = useState(false);
  const [savingIntegrations, setSavingIntegrations] = useState(false);
  const [copiedKey, setCopiedKey] = useState(null);
  
  // Advanced state
  const [revenuePerVisit, setRevenuePerVisit] = useState(150);
  const [recallDays, setRecallDays] = useState("30, 60, 90");
  const [benchmarkOptIn, setBenchmarkOptIn] = useState(false);

  // Outbound Webhook state
  const [outboundWebhookUrl, setOutboundWebhookUrl] = useState("");
  const [outboundWebhookSecret, setOutboundWebhookSecret] = useState("");
  const [outboundWebhookEvents, setOutboundWebhookEvents] = useState([
    "call.completed",
    "appointment.booked",
    "appointment.cancelled",
    "patient.created"
  ]);
  const [showWebhookSecret, setShowWebhookSecret] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState(false);
  const [webhookTestResult, setWebhookTestResult] = useState(null);

  // API Key Management state
  const [apiKeys, setApiKeys] = useState([]);
  const [loadingApiKeys, setLoadingApiKeys] = useState(false);
  const [showNewKeyModal, setShowNewKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyScopes, setNewKeyScopes] = useState(["read", "write"]);
  const [creatingKey, setCreatingKey] = useState(false);
  const [createdKeyData, setCreatedKeyData] = useState(null);
  const [revokingKeyId, setRevokingKeyId] = useState(null);

  // Danger Zone: Data Export & Soft Delete states
  const [exportingFormat, setExportingFormat] = useState(null); // null | 'json' | 'csv'
  const [showSoftDeleteModal, setShowSoftDeleteModal] = useState(false);
  const [softDeleteConfirmation, setSoftDeleteConfirmation] = useState("");
  const [softDeleteReason, setSoftDeleteReason] = useState("");
  const [isSoftDeleting, setIsSoftDeleting] = useState(false);

  // Factory Reset
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [isWiping, setIsWiping] = useState(false);

  const getClinicId = () => {
    const info = JSON.parse(localStorage.getItem("clinic-info") || sessionStorage.getItem("clinic-info") || "{}");
    return info.clinicId || "d3b07384-d113-46a6-a719-38cf89235d54";
  };

  const fetchApiKeys = useCallback(async () => {
    setLoadingApiKeys(true);
    try {
      const cid = getClinicId();
      const res = await api.get(`/clinics/${cid}/api-keys`);
      setApiKeys(res.data?.data || []);
    } catch (err) {
      console.warn("[Settings] API Keys fetch error:", err.message);
    } finally {
      setLoadingApiKeys(false);
    }
  }, []);

  useEffect(() => {
    fetchClinic();
    fetchIntegrationsStatus();
    fetchApiKeys();
    
    // Check url query parameters for active tab, checkout status, and google oauth
    const params = new URLSearchParams(window.location.search);
    const checkoutStatus = params.get("checkout");
    const googleStatus = params.get("google");
    const tabParam = params.get("tab");
    
    if (tabParam) {
      const allowedTabs = ["profile", "doctor", "team", "hours", "types", "agent_builder", "ehr", "integrations", "notifications", "advanced", "security", "danger"];
      if (!isOwner && !allowedTabs.includes(tabParam)) {
        setActiveTab("profile");
      } else {
        setActiveTab(tabParam);
      }
    }
    
    if (checkoutStatus === "success") {
      setMsg({ type: "success", text: "Subscription successfully updated! Thank you for your partnership." });
      window.history.replaceState({}, document.title, window.location.pathname + (tabParam ? `?tab=${tabParam}` : ""));
    } else if (checkoutStatus === "cancel") {
      setMsg({ type: "error", text: "Checkout cancelled. Feel free to upgrade at any time." });
      window.history.replaceState({}, document.title, window.location.pathname + (tabParam ? `?tab=${tabParam}` : ""));
    } else if (googleStatus === "success") {
      setMsg({ type: "success", text: "Google Calendar connected and synced successfully!" });
      window.history.replaceState({}, document.title, window.location.pathname + (tabParam ? `?tab=${tabParam}` : ""));
    } else if (googleStatus === "error") {
      const errorDetail = params.get("msg") || "OAuth authorization failed";
      setMsg({ type: "error", text: `Google Calendar connection error: ${errorDetail}` });
      window.history.replaceState({}, document.title, window.location.pathname + (tabParam ? `?tab=${tabParam}` : ""));
    }
  }, [fetchApiKeys, isOwner]);

  useEffect(() => {
    if (activeTab === "advanced") {
      fetchApiKeys();
    }
  }, [activeTab, fetchApiKeys]);

  const fetchIntegrationsStatus = async () => {
    setLoadingIntegrations(true);
    try {
      const res = await api.get("/integrations/status");
      if (res.data?.data) {
        setIntegrationsStatus(res.data.data);
      }
    } catch (err) {
      console.warn("[Settings] Integrations status fetch error:", err.message);
    } finally {
      setLoadingIntegrations(false);
    }
  };

  const fetchClinic = async () => {
    try {
      const cid = getClinicId();
      const res = await api.get(`/clinics/${cid}`);
      const data = res.data.data || res.data;
      setClinic(data);

      // Map DB states to local form states
      setName(data.name || "Sunrise Medical Clinic");
      const clinicSpecialty = data.specialty || "General Practice";
      setSpecialty(clinicSpecialty);
      setIsCustomSpecialty(Boolean(clinicSpecialty && !SPECIALTIES.includes(clinicSpecialty) && clinicSpecialty !== "Other"));
      setAddress(data.address || "100 Michigan Avenue");
      setSuite(data.suite || "Suite 400");
      setCity(data.city || "Chicago");
      setState(data.state || "IL");
      setZipCode(data.zip_code || "60601");
      setTimezone(data.timezone || "America/Chicago");
      setPhoneNumber(data.phone_number || "+1 (555) 123-4567");
      setOwnerEmail(data.owner_email || "admin@sunriseclinic.com");
      setEmergencyProtocols(data.emergency_protocols || "If caller reports chest pain, severe shortness of breath, sudden numbness, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest emergency department.");
      setTransferPhoneNumber(data.transfer_phone_number || data.primary_doctor_phone || data.phone_number || "+1 (555) 987-6543");
      
      setDoctorName(data.primary_doctor_name || "");
      setDoctorCredentials(data.primary_doctor_credentials || "");
      setDoctorPhone(data.primary_doctor_phone || "");
      setNpiNumber(data.npi_number || "");
      setMedicalLicense(data.medical_license || "");

      // Handle business hours parsing
      setHours(parseBusinessHoursData(data.business_hours));

      // Handle appointment types
      if (Array.isArray(data.appointment_types) && data.appointment_types.length > 0) {
        setApptTypes(data.appointment_types.map(t => ({
          name: t.name || "Appointment",
          duration: parseInt(t.duration_minutes || t.duration) || 30,
          duration_minutes: parseInt(t.duration_minutes || t.duration) || 30,
          fee: parseFloat(t.fee !== undefined ? t.fee : (t.price !== undefined ? t.price : 0)) || 0
        })));
      } else {
        setApptTypes([
          { name: "Initial Evaluation", duration: 60, duration_minutes: 60, fee: 150 },
          { name: "Follow-up", duration: 30, duration_minutes: 30, fee: 75 }
        ]);
      }

      setTelnyxNumber(data.telnyx_number || "+15755734355");
      setTwilioNumber(data.twilio_number || data.phone_number || "+15551234567");
      setGoogleCalendarId(data.google_calendar_id || "primary");
      setRevenuePerVisit(data.monthly_revenue_per_visit || 150);
      setRecallDays(
        Array.isArray(data.recall_days)
          ? data.recall_days.join(", ")
          : (typeof data.recall_days === "string" ? data.recall_days : "30, 60, 90")
      );
      setBenchmarkOptIn(data.benchmark_opt_in || false);
      setOutboundWebhookUrl(data.webhook_url || "");
      setOutboundWebhookSecret(data.webhook_secret || "");
      if (Array.isArray(data.webhook_events) && data.webhook_events.length > 0) {
        setOutboundWebhookEvents(data.webhook_events);
      } else {
        setOutboundWebhookEvents(["call.completed", "appointment.booked", "appointment.cancelled", "patient.created"]);
      }
      if (data.notifications_config) {
        setNotifConfig({ ...DEFAULT_NOTIFICATIONS_CONFIG, ...data.notifications_config });
      }
    } catch (err) {
      console.error("Settings fetch error:", err.message);
      setMsg({ type: "error", text: "Failed to load clinic settings." });
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e) => {
    if (e) e.preventDefault();
    setSaving(true);
    setMsg(null);

    // Validate doctor fields before submitting
    const errors = {};

    // Validate NPI (if non-empty, must be 10 numeric digits)
    if (npiNumber && npiNumber.trim()) {
      const cleanNpi = npiNumber.replace(/\D/g, "");
      if (cleanNpi.length !== 10) {
        errors.npiNumber = "NPI Number must be exactly 10 numeric digits.";
      }
    }

    // Validate Doctor Phone (if non-empty, must have valid 10-15 digits)
    if (doctorPhone && doctorPhone.trim()) {
      const digits = doctorPhone.replace(/\D/g, "");
      if (digits.length < 10 || digits.length > 15) {
        errors.doctorPhone = "Doctor direct phone must contain a valid 10-15 digit phone number.";
      }
    }

    // Validate Medical License (if non-empty, 2-50 chars)
    if (medicalLicense && medicalLicense.trim()) {
      const lic = medicalLicense.trim();
      if (lic.length < 2 || lic.length > 50) {
        errors.medicalLicense = "Medical license must be between 2 and 50 characters.";
      } else if (!/^[A-Za-z0-9\-\.\/\s]+$/.test(lic)) {
        errors.medicalLicense = "Medical license contains invalid characters. Use letters, numbers, hyphens or dots.";
      }
    }

    // Validate Doctor Name
    if (doctorName && doctorName.trim().length > 120) {
      errors.doctorName = "Doctor name cannot exceed 120 characters.";
    }

    // Validate Doctor Credentials
    if (doctorCredentials && doctorCredentials.trim().length > 60) {
      errors.doctorCredentials = "Doctor credentials cannot exceed 60 characters.";
    }

    if (Object.keys(errors).length > 0) {
      setDoctorErrors(errors);
      setMsg({ type: "error", text: "Please fix the validation errors in the Doctor Info tab before saving." });
      setSaving(false);
      return;
    }
    setDoctorErrors({});

    // Validate Clinic Profile fields
    const pErrors = {};
    if (!name || !name.trim()) {
      pErrors.name = "Clinic Legal / Display Name is required.";
    } else if (name.trim().length > 150) {
      pErrors.name = "Clinic Name cannot exceed 150 characters.";
    }

    if (!city || !city.trim()) {
      pErrors.city = "City / Municipality is required.";
    } else if (city.trim().length > 100) {
      pErrors.city = "City cannot exceed 100 characters.";
    }

    if (!ownerEmail || !ownerEmail.trim()) {
      pErrors.ownerEmail = "Owner / Admin Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(ownerEmail.trim())) {
      pErrors.ownerEmail = "Please enter a valid Owner Email address format (e.g. admin@clinic.com).";
    }

    if (phoneNumber && phoneNumber.trim()) {
      const digits = phoneNumber.replace(/\D/g, "");
      if (digits.length < 10 || digits.length > 15) {
        pErrors.phoneNumber = "Patient Direct Phone must contain a valid 10-15 digit phone number.";
      }
    }

    if (specialty && specialty.trim().length > 100) {
      pErrors.specialty = "Medical Specialty cannot exceed 100 characters.";
    }

    if (Object.keys(pErrors).length > 0) {
      setProfileErrors(pErrors);
      setMsg({ type: "error", text: "Please fix the validation errors in Clinic Profile before saving." });
      setSaving(false);
      return;
    }
    setProfileErrors({});

    try {
      const cid = getClinicId();
      const info = JSON.parse(localStorage.getItem("clinic-info") || sessionStorage.getItem("clinic-info") || "{}");

      // Validate business hours
      for (const day of ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]) {
        const d = hours[day];
        if (d && d.enabled) {
          if (!d.start || !d.end || d.start >= d.end) {
            const dayLabel = DAYS_CONFIG.find(dc => dc.key === day)?.label || day;
            setMsg({ type: "error", text: `Invalid business hours for ${dayLabel}: Closing time (${d.end || "empty"}) must be after opening time (${d.start || "empty"}).` });
            setSaving(false);
            return;
          }
        }
      }

      // Formulate business hours in DB format
      const dbBusinessHours = formatBusinessHoursForDb(hours);

      // Parse recall days back to array of ints
      const parsedRecallDays = recallDays
        .split(",")
        .map(x => parseInt(x.trim()))
        .filter(x => !isNaN(x));

      const updates = {
        name: name.trim(),
        specialty: specialty.trim(),
        address: (address || "").trim(),
        suite: (suite || "").trim(),
        city: city.trim(),
        state: (state || "").trim(),
        zip_code: (zipCode || "").trim(),
        timezone: timezone.trim(),
        phone_number: phoneNumber.trim(),
        owner_email: ownerEmail.trim().toLowerCase(),
        primary_doctor_name: doctorName.trim(),
        primary_doctor_credentials: doctorCredentials.trim(),
        primary_doctor_phone: doctorPhone.trim(),
        npi_number: npiNumber.trim(),
        medical_license: medicalLicense.trim(),
        emergency_protocols: (emergencyProtocols || "").trim(),
        transfer_phone_number: (transferPhoneNumber || "").trim(),
        business_hours: dbBusinessHours,
        appointment_types: apptTypes.map(t => ({
          name: t.name.trim(),
          duration: Math.max(5, parseInt(t.duration_minutes || t.duration) || 30),
          duration_minutes: Math.max(5, parseInt(t.duration_minutes || t.duration) || 30),
          fee: Math.max(0, parseFloat(t.fee !== undefined ? t.fee : (t.price !== undefined ? t.price : 0)) || 0)
        })),
        telnyx_number: telnyxNumber.trim(),
        twilio_number: twilioNumber.trim(),
        google_calendar_id: googleCalendarId.trim(),
        monthly_revenue_per_visit: parseInt(revenuePerVisit) || 150,
        recall_days: parsedRecallDays,
        benchmark_opt_in: benchmarkOptIn,
        webhook_url: (outboundWebhookUrl || "").trim(),
        webhook_secret: (outboundWebhookSecret || "").trim(),
        webhook_events: outboundWebhookEvents,
        notifications_config: notifConfig
      };

      await api.put(`/clinics/${cid}`, updates);
      setMsg({ type: "success", text: "Clinic profile & settings saved successfully to PostgreSQL database!" });
      
      // Update local storage and session storage so sidebar & header update immediately
      const updatedInfo = {
        ...info,
        clinicId: cid,
        clinicName: name.trim(),
        timezone: timezone.trim(),
        ownerEmail: ownerEmail.trim().toLowerCase()
      };
      localStorage.setItem("clinic-info", JSON.stringify(updatedInfo));
      sessionStorage.setItem("clinic-info", JSON.stringify(updatedInfo));

      // Broadcast custom event so sidebar/header react immediately without page reload
      window.dispatchEvent(new CustomEvent("clinic-updated", { detail: updatedInfo }));

      // Refresh data
      await fetchClinic();
      await fetchIntegrationsStatus();
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || err.response?.data?.error || err.message });
    } finally {
      setSaving(false);
    }
  };

  const handleTestWebhook = async () => {
    const url = (outboundWebhookUrl || "").trim();
    if (!url) {
      setMsg({ type: "error", text: "Please enter a valid Webhook URL to test." });
      return;
    }
    setTestingWebhook(true);
    setWebhookTestResult(null);
    try {
      const cid = getClinicId();
      const res = await api.post(`/clinics/${cid}/test-webhook`, {
        webhook_url: url,
        webhook_secret: (outboundWebhookSecret || "").trim()
      });
      setWebhookTestResult({
        success: true,
        statusCode: res.data?.statusCode || 200,
        message: res.data?.message || "Webhook test ping successfully delivered.",
        preview: res.data?.responsePreview || ""
      });
      setMsg({ type: "success", text: "Webhook test ping delivered successfully!" });
    } catch (err) {
      const errDetail = err.response?.data?.detail || err.response?.data?.error || err.message;
      setWebhookTestResult({
        success: false,
        message: errDetail
      });
      setMsg({ type: "error", text: `Webhook test failed: ${errDetail}` });
    } finally {
      setTestingWebhook(false);
    }
  };

  const handleGenerateWebhookSecret = () => {
    const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    let secret = "whsec_";
    for (let i = 0; i < 32; i++) {
      secret += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    setOutboundWebhookSecret(secret);
  };

  const handleToggleWebhookEvent = (evName) => {
    setOutboundWebhookEvents(prev =>
      prev.includes(evName) ? prev.filter(x => x !== evName) : [...prev, evName]
    );
  };

  const handleCreateApiKey = async (e) => {
    if (e) e.preventDefault();
    if (!newKeyName.trim()) {
      alert("Please enter a name for the API Key.");
      return;
    }
    setCreatingKey(true);
    try {
      const cid = getClinicId();
      const res = await api.post(`/clinics/${cid}/api-keys`, {
        name: newKeyName.trim(),
        scopes: newKeyScopes
      });
      const created = res.data?.data;
      setCreatedKeyData(created);
      setNewKeyName("");
      setNewKeyScopes(["read", "write"]);
      setShowNewKeyModal(false);
      await fetchApiKeys();
      setMsg({ type: "success", text: `API key '${created?.name}' generated successfully.` });
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || err.message });
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeApiKey = async (keyId, keyName) => {
    if (!window.confirm(`Are you sure you want to permanently revoke API key '${keyName}'? Any applications or integrations using this key will immediately lose access.`)) {
      return;
    }
    setRevokingKeyId(keyId);
    try {
      const cid = getClinicId();
      await api.delete(`/clinics/${cid}/api-keys/${keyId}`);
      setApiKeys(prev => prev.filter(k => k.id !== keyId));
      setMsg({ type: "success", text: `API key '${keyName}' was revoked successfully.` });
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || err.message });
    } finally {
      setRevokingKeyId(null);
    }
  };

  const handleCopy = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const connectGoogle = () => {
    const token = localStorage.getItem('sb-token') || sessionStorage.getItem('sb-token') || localStorage.getItem('sb-access-token');
    const apiBase = import.meta.env.VITE_API_URL || 'https://clinic-os-production.up.railway.app/api/v1';
    const oauthBase = apiBase.endsWith('/api/v1') ? apiBase.slice(0, -7) : apiBase;
    window.location.href = `${oauthBase}/auth/google?token=${encodeURIComponent(token || '')}`;
  };

  const handleDisconnectGoogle = async () => {
    if (!window.confirm("Are you sure you want to disconnect Google Calendar? The AI voice receptionist will no longer sync appointments to Google Calendar.")) return;
    setDisconnectingGoogle(true);
    setMsg(null);
    try {
      const res = await api.post("/integrations/google/disconnect");
      setMsg({ type: "success", text: res.data?.message || "Google Calendar disconnected successfully." });
      await fetchClinic();
      await fetchIntegrationsStatus();
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || err.message });
    } finally {
      setDisconnectingGoogle(false);
    }
  };

  const handleSyncCalle = async () => {
    setSyncingCalle(true);
    setMsg(null);
    try {
      // Actually verify CALL-E connection — don't fake success
      const res = await api.get('/calle/status');
      const status = res.data;
      if (status?.configured || status?.live_mode) {
        setMsg({ type: "success", text: "CALL-E API Engine verified successfully! Live mode active." });
      } else {
        setMsg({ type: "warning", text: "CALL-E connected but not in live mode. Check CALLE_DRY_RUN setting." });
      }
      await fetchClinic();
      await fetchIntegrationsStatus();
    } catch (err) {
      setMsg({ type: "error", text: `CALL-E connection failed: ${err.response?.data?.detail || err.message}` });
    } finally {
      setSyncingCalle(false);
    }
  };

  const handleTestIntegration = async (serviceName) => {
    setTestingService(serviceName);
    setTestResult(null);
    setMsg(null);
    try {
      const res = await api.post(`/integrations/test/${serviceName}`);
      const result = res.data;
      setTestResult({ service: serviceName, success: result.success, message: result.message });
      if (result.success) {
        setMsg({ type: "success", text: `✓ ${result.message}` });
      } else {
        setMsg({ type: "error", text: `✗ ${result.message}` });
      }
      await fetchIntegrationsStatus();
    } catch (err) {
      const errorText = err.response?.data?.detail || err.response?.data?.error || err.message;
      setTestResult({ service: serviceName, success: false, message: errorText });
      setMsg({ type: "error", text: `Verification failed: ${errorText}` });
    } finally {
      setTestingService(null);
    }
  };

  const handleOpenStripePortal = async () => {
    setOpeningPortal(true);
    setMsg(null);
    try {
      const res = await api.post("/billing/portal", { return_url: window.location.href });
      if (res.data?.portalUrl) {
        window.location.href = res.data.portalUrl;
      } else if (res.data?.url) {
        window.location.href = res.data.url;
      } else {
        setMsg({ type: "success", text: "Stripe Billing portal session generated." });
      }
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || "Could not open Stripe Billing Portal." });
    } finally {
      setOpeningPortal(false);
    }
  };

  const handleSaveIntegrations = async () => {
    setSavingIntegrations(true);
    setMsg(null);
    try {
      const payload = {
        telnyx_number: telnyxNumber,
        twilio_number: twilioNumber,
        google_calendar_id: googleCalendarId
      };
      const res = await api.put("/integrations/settings", payload);
      setMsg({ type: "success", text: res.data?.message || "Integration settings saved successfully!" });
      await fetchClinic();
      await fetchIntegrationsStatus();
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || err.message });
    } finally {
      setSavingIntegrations(false);
    }
  };

  const handleExportClinicData = async (format = "json") => {
    setExportingFormat(format);
    setMsg(null);
    try {
      const cid = getClinicId();
      const res = await api.get(`/clinics/${cid}/export?format=${format}`, {
        responseType: "blob"
      });

      const mimeType = format === "json" ? "application/json" : "application/zip";
      const blob = new Blob([res.data], { type: mimeType });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.style.display = "none";
      a.href = url;
      const dateStr = new Date().toISOString().split("T")[0];
      a.download = `clinic_export_${cid}_${dateStr}.${format === "json" ? "json" : "zip"}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setMsg({
        type: "success",
        text: `Full clinic data exported successfully as ${format.toUpperCase()} archive.`
      });
    } catch (err) {
      let errorMsg = "Failed to export clinic records.";
      if (err.response?.data instanceof Blob) {
        try {
          const text = await err.response.data.text();
          const parsed = JSON.parse(text);
          errorMsg = parsed.detail || parsed.error || errorMsg;
        } catch (_) {}
      } else if (err.response?.data?.detail || err.response?.data?.error) {
        errorMsg = err.response.data.detail || err.response.data.error;
      } else if (err.message) {
        errorMsg = err.message;
      }
      setMsg({ type: "error", text: errorMsg });
    } finally {
      setExportingFormat(null);
    }
  };

  const handleSoftDeleteClinic = async () => {
    setIsSoftDeleting(true);
    setMsg(null);
    try {
      const cid = getClinicId();
      const res = await api.post(`/clinics/${cid}/soft-delete`, {
        confirmation: softDeleteConfirmation.trim(),
        reason: softDeleteReason.trim() || undefined
      });
      setMsg({
        type: "success",
        text: res.data?.message || "Clinic account has been soft-deleted and deactivated successfully."
      });
      setShowSoftDeleteModal(false);
      setSoftDeleteConfirmation("");
      setSoftDeleteReason("");
      await fetchClinic();
    } catch (err) {
      setMsg({
        type: "error",
        text: err.response?.data?.detail || err.response?.data?.error || err.message
      });
    } finally {
      setIsSoftDeleting(false);
    }
  };

  const handleFactoryReset = async () => {
    setIsWiping(true);
    setMsg(null);
    try {
      const cid = getClinicId();
      await api.post(`/clinics/${cid}/factory-reset`, { confirmation: deleteConfirmation.trim() });
      setMsg({ type: "success", text: "Factory reset complete! Reloading workspace..." });
      setShowDeleteModal(false);
      setDeleteConfirmation("");
      setTimeout(() => window.location.reload(), 1500);
    } catch (err) {
      setMsg({ type: "error", text: err.response?.data?.detail || err.response?.data?.error || err.message });
      setIsWiping(false);
      setShowDeleteModal(false);
      setDeleteConfirmation("");
    }
  };

  const handleAddApptType = () => {
    const trimmed = newTypeName.trim();
    if (!trimmed) {
      setMsg({ type: "error", text: "Please enter a name for the appointment type." });
      return;
    }
    const exists = apptTypes.some(t => t.name.toLowerCase() === trimmed.toLowerCase());
    if (exists) {
      setMsg({ type: "error", text: `Appointment type "${trimmed}" already exists.` });
      return;
    }
    const dur = Math.max(5, parseInt(newTypeDuration) || 30);
    const fee = Math.max(0, parseFloat(newTypeFee) || 0);
    setApptTypes([...apptTypes, {
      name: trimmed,
      duration: dur,
      duration_minutes: dur,
      fee: fee
    }]);
    setNewTypeName("");
    setNewTypeDuration(30);
    setNewTypeFee(100);
    setMsg({ type: "success", text: `Added "${trimmed}" (${dur} min, $${fee}). Remember to click "Save All Settings".` });
  };

  const handleRemoveApptType = (index) => {
    if (apptTypes.length <= 1) {
      setMsg({ type: "error", text: "At least one active appointment type is required." });
      return;
    }
    const target = apptTypes[index];
    const filtered = apptTypes.filter((_, idx) => idx !== index);
    setApptTypes(filtered);
    if (editingApptIdx === index) {
      setEditingApptIdx(null);
      setEditingAppt(null);
    }
    setMsg({ type: "info", text: `Removed "${target?.name || 'appointment type'}". Click "Save All Settings" to apply.` });
  };

  const handleStartEditApptType = (index) => {
    const target = apptTypes[index];
    setEditingApptIdx(index);
    setEditingAppt({
      name: target.name,
      duration: target.duration_minutes || target.duration || 30,
      duration_minutes: target.duration_minutes || target.duration || 30,
      fee: target.fee !== undefined ? target.fee : (target.price !== undefined ? target.price : 0)
    });
  };

  const handleSaveEditApptType = () => {
    if (editingApptIdx === null || !editingAppt) return;
    const trimmed = (editingAppt.name || "").trim();
    if (!trimmed) {
      setMsg({ type: "error", text: "Appointment type name cannot be empty." });
      return;
    }
    const exists = apptTypes.some((t, idx) => idx !== editingApptIdx && t.name.toLowerCase() === trimmed.toLowerCase());
    if (exists) {
      setMsg({ type: "error", text: `Another appointment type named "${trimmed}" already exists.` });
      return;
    }
    const dur = Math.max(5, parseInt(editingAppt.duration_minutes || editingAppt.duration) || 30);
    const fee = Math.max(0, parseFloat(editingAppt.fee !== undefined ? editingAppt.fee : editingAppt.price) || 0);
    const updated = [...apptTypes];
    updated[editingApptIdx] = {
      name: trimmed,
      duration: dur,
      duration_minutes: dur,
      fee: fee
    };
    setApptTypes(updated);
    setEditingApptIdx(null);
    setEditingAppt(null);
    setMsg({ type: "success", text: `Updated "${trimmed}". Remember to click "Save All Settings".` });
  };

  const handleCancelEditApptType = () => {
    setEditingApptIdx(null);
    setEditingAppt(null);
  };

  const handleHourChange = (day, field, val) => {
    setHours(prev => ({
      ...prev,
      [day]: {
        ...prev[day],
        [field]: val
      }
    }));
  };

  const handleCopyMonToWeekdays = () => {
    const mon = hours.mon || DEFAULT_HOURS.mon;
    setHours(prev => ({
      ...prev,
      tue: { ...mon },
      wed: { ...mon },
      thu: { ...mon },
      fri: { ...mon }
    }));
    setMsg({ type: "success", text: "Copied Monday schedule to Tuesday through Friday. Click 'Save All Settings' to persist changes." });
  };

  const handleApplyStandardMedicalPreset = () => {
    setHours({
      mon: { enabled: true, start: "08:00", end: "17:00" },
      tue: { enabled: true, start: "08:00", end: "17:00" },
      wed: { enabled: true, start: "08:00", end: "17:00" },
      thu: { enabled: true, start: "08:00", end: "17:00" },
      fri: { enabled: true, start: "08:00", end: "17:00" },
      sat: { enabled: true, start: "09:00", end: "13:00" },
      sun: { enabled: false, start: "08:00", end: "17:00" }
    });
    setMsg({ type: "success", text: "Applied standard medical schedule: Mon–Fri 8am–5pm, Sat 9am–1pm, Sun Closed. Click 'Save Business Hours & Protocols' to persist." });
  };

  const handleApplyPreset = (start, end, weekendsEnabled = false) => {
    setHours(prev => ({
      ...prev,
      mon: { enabled: true, start, end },
      tue: { enabled: true, start, end },
      wed: { enabled: true, start, end },
      thu: { enabled: true, start, end },
      fri: { enabled: true, start, end },
      sat: { ...(prev.sat || DEFAULT_HOURS.sat), enabled: weekendsEnabled, start, end },
      sun: { ...(prev.sun || DEFAULT_HOURS.sun), enabled: weekendsEnabled, start, end }
    }));
    setMsg({ type: "success", text: `Applied ${start}–${end} (${weekendsEnabled ? "7 Days" : "Mon–Fri"}) schedule preset. Click 'Save Business Hours & Protocols' to persist.` });
  };

  const apiUrl = import.meta.env.VITE_API_URL || "http://localhost:3000/api/v1";
  const webhookBase = apiUrl.endsWith("/api/v1") ? apiUrl.slice(0, -7) : apiUrl;
  const webhookUrl = `${webhookBase}/api/v1/calle/webhook`;
  const telnyxWebhookUrl = `${webhookBase}/webhooks/telnyx/sms`;
  const twilioSmsWebhookUrl = `${webhookBase}/webhooks/twilio/sms`;
  const twilioVoiceWebhookUrl = `${webhookBase}/webhooks/twilio/voice`;

  const isGoogleConnected = Boolean(integrationsStatus?.google_calendar?.connected ?? clinic?.google_refresh_token);
  const isTelnyxConnected = Boolean(integrationsStatus?.telnyx?.connected ?? (clinic?.telnyx_number && String(clinic.telnyx_number).trim().length >= 10));
  const isCalleConnected = Boolean(integrationsStatus?.calle?.connected ?? integrationsStatus?.calle?.is_configured ?? false);
  const isTwilioConnected = Boolean(integrationsStatus?.twilio?.connected ?? (clinic?.twilio_number || integrationsStatus?.twilio?.is_configured));
  const isStripeConnected = Boolean(integrationsStatus?.stripe?.connected ?? (clinic?.stripe_customer_id || clinic?.subscription_status === "active" || clinic?.stripe_subscription_status === "active"));

  const allTabs = [
    { id: "profile", label: t.profile || "Clinic Profile", icon: MapPin, restricted: false },
    { id: "doctor", label: t.doctor_info || "Doctor Info", icon: User, restricted: false },
    { id: "team", label: t.team_staff || "Team & Staff", icon: Users, restricted: true },
    { id: "hours", label: t.hours || "Business Hours", icon: Clock, restricted: false },
    { id: "types", label: t.types || "Appointment Types", icon: Briefcase, restricted: false },
    { id: "agent_builder", label: t.agent_builder_tab || "Agent Builder", icon: Bot, restricted: false },
    { id: "ehr", label: t.ehr_sync || "EHR Sync", icon: Database, restricted: true },
    { id: "integrations", label: t.integrations || "Integrations", icon: Wifi, restricted: true },
    { id: "notifications", label: t.notifications || "Notifications", icon: Bell, restricted: false },
    { id: "advanced", label: t.advanced || "Advanced Setup", icon: Sliders, restricted: true },
    { id: "security", label: t.security || "Security & Auditing", icon: Shield, restricted: true },
    { id: "danger", label: t.danger || "Danger Zone", icon: AlertTriangle, restricted: true }
  ].filter(Boolean);

  const tabs = allTabs.filter(tab => !tab.restricted || isOwner);

  const categories = [
    {
      id: "general",
      title: t.general_settings || "General Settings",
      tabIds: ["profile", "doctor", "team", "hours", "types"]
    },
    {
      id: "ai_receptionist",
      title: t.ai_receptionist || "AI Receptionist",
      tabIds: ["agent_builder", "notifications"]
    },
    {
      id: "integrations",
      title: t.integrations_sync || "Integrations & Sync",
      tabIds: ["ehr", "integrations"]
    },
    {
      id: "billing_security",
      title: t.security || "Security & Auditing",
      tabIds: ["security", "advanced", "danger"]
    }
  ];

  const filteredCategories = categories.map(cat => ({
    ...cat,
    tabs: tabs.filter(t => cat.tabIds.includes(t.id))
  })).filter(cat => cat.tabs.length > 0);

  if (loading) {
    return (
      <div className="h-96 flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* ── Page Header ──────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="page-header-title">
            {t.clinic_settings || "Clinic Settings"}
          </h1>
          <p className="page-header-sub">
            {t.settings_sub || "Configure profile, hours, calendar integrations, and AI agent prompt data."}
          </p>
        </div>
        
        {activeTab !== "danger" && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary self-start sm:self-auto flex items-center gap-2"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Save className="w-4 h-4" />
            )}
            {saving ? t.saving || "Saving Changes..." : t.save_all || "Save All Settings"}
          </button>
        )}
      </div>

      {/* ── Alert Toast ──────────────────────────────────────── */}
      {msg && (
        <div
          className={`px-4 py-3 rounded-[0.75rem] text-sm font-semibold flex items-center justify-between gap-2 transition-all animate-in fade-in slide-in-from-top-1 ${
            msg.type === "success"
              ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]"
              : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
          }`}
        >
          <div className="flex items-center gap-2">
            {msg.type === "success" ? (
              <CheckCircle className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 flex-shrink-0" />
            )}
            <span>{msg.text}</span>
          </div>
          <button
            onClick={() => setMsg(null)}
            className="text-xs opacity-70 hover:opacity-100 font-bold px-2 py-0.5"
          >
            ✕
          </button>
        </div>
      )}

      {/* ── MAIN SETTINGS PANEL ──────────────────────────────── */}
      <div className="grid grid-cols-1 xl:grid-cols-[220px_1fr_240px] gap-5">
        
        {/* Left Column: Vertical Sidebar for Desktop */}
        <div className="hidden xl:flex flex-col gap-5 pr-4 border-r border-surface-container w-[220px] flex-shrink-0">
          {filteredCategories.map((cat) => (
            <div key={cat.id} className="space-y-1">
              <h4 className="text-[10px] font-bold text-on-surface-variant/40 uppercase tracking-widest px-3 mb-1">
                {cat.title}
              </h4>
              <div className="space-y-0.5">
                {cat.tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => {
                        setActiveTab(tab.id);
                        setMsg(null);
                      }}
                      className={`flex items-center gap-3 w-full text-left py-2 px-3 rounded-xl text-xs font-bold transition-all ${
                        isActive
                          ? "bg-[#edf7e0] text-[#396a00] shadow-sm"
                          : "text-on-surface-variant hover:bg-surface-container animate-in duration-150"
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      <span>{tab.label}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* Center Column: Mobile Tab Selector (Dropdown) & Active Tab Card */}
        <div className="space-y-4 min-w-0 flex-1">
          <div className="block xl:hidden">
            <label className="overline mb-1.5 block">Settings Section</label>
            <select
              value={activeTab}
              onChange={(e) => {
                setActiveTab(e.target.value);
                setMsg(null);
              }}
              className="input-field w-full"
            >
              {filteredCategories.map((cat) => (
                <optgroup key={cat.id} label={cat.title}>
                  {cat.tabs.map((tab) => (
                    <option key={tab.id} value={tab.id}>
                      {tab.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <div className="card p-4 sm:p-6 min-h-[200px]">
          
          {/* TAB 1: PROFILE */}
          {activeTab === "profile" && (
            <div className="space-y-6">
              <div className="border-b border-surface-container pb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div>
                  <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                    <Building className="w-5 h-5 text-primary" />
                    Clinic Profile & Identity
                  </h3>
                  <p className="text-xs text-on-surface-variant mt-1">General practice information, contact channels, and regional timezone configuration.</p>
                </div>
                <div className="flex items-center gap-2 self-start sm:self-auto">
                  <span className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md bg-primary/10 text-primary border border-primary/20">
                    PostgreSQL Persisted
                  </span>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="btn-primary flex items-center gap-2 text-xs py-2 px-4"
                  >
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    <span>{saving ? "Saving Changes..." : "Save Clinic Profile"}</span>
                  </button>
                </div>
              </div>

              <div className="space-y-5">
                {/* Field 1: Clinic Legal / Display Name */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="overline">Clinic Legal / Display Name *</label>
                    <span className="text-[10px] text-on-surface-variant/70 font-mono">{name.length}/150 chars</span>
                  </div>
                  <div className={`flex items-center gap-2 input-field bg-surface-container-highest transition-colors ${
                    profileErrors.name ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                  }`}>
                    <Building className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="text"
                      value={name}
                      maxLength={150}
                      onChange={(e) => {
                        setName(e.target.value);
                        if (profileErrors.name) setProfileErrors(prev => ({ ...prev, name: null }));
                      }}
                      className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface"
                      placeholder="e.g. Sunrise Medical Clinic"
                      required
                    />
                  </div>
                  {profileErrors.name && (
                    <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {profileErrors.name}
                    </p>
                  )}
                  <p className="text-[11px] text-on-surface-variant mt-1">Official clinic brand name displayed on the dashboard, patient portal, and spoken by the AI receptionist.</p>
                </div>

                {/* Field 2: Medical Specialty */}
                <div>
                  <label className="overline mb-1.5 block">Medical Specialty</label>
                  <select
                    value={isCustomSpecialty ? "Other" : specialty}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === "Other") {
                        setIsCustomSpecialty(true);
                        setSpecialty("");
                      } else {
                        setIsCustomSpecialty(false);
                        setSpecialty(val);
                      }
                      if (profileErrors.specialty) setProfileErrors(prev => ({ ...prev, specialty: null }));
                    }}
                    className={`input-field appearance-none cursor-pointer ${
                      profileErrors.specialty ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                    }`}
                  >
                    <option value="">Select Medical Specialty</option>
                    {SPECIALTIES.map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                    {specialty && !SPECIALTIES.includes(specialty) && !isCustomSpecialty && (
                      <option value={specialty}>{specialty}</option>
                    )}
                  </select>
                  {isCustomSpecialty && (
                    <div className="mt-2">
                      <input
                        type="text"
                        value={specialty}
                        maxLength={100}
                        onChange={(e) => {
                          setSpecialty(e.target.value);
                          if (profileErrors.specialty) setProfileErrors(prev => ({ ...prev, specialty: null }));
                        }}
                        placeholder="Type custom clinical specialty..."
                        className="input-field text-xs bg-surface-container-highest"
                      />
                    </div>
                  )}
                  {profileErrors.specialty && (
                    <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {profileErrors.specialty}
                    </p>
                  )}
                  <p className="text-[11px] text-on-surface-variant mt-1">Clinical domain used for AI triage protocols, vocabulary, and specialty injection.</p>
                </div>

                {/* Field 3: Physical Address Details (Street, Suite, City, State, Zip) */}
                <div className="p-4 rounded-xl bg-surface-container-low border border-surface-container space-y-3.5">
                  <div className="flex items-center justify-between border-b border-surface-container pb-2">
                    <p className="overline text-[11px] flex items-center gap-1.5 text-on-surface font-bold">
                      <MapPin className="w-3.5 h-3.5 text-primary" /> Physical Clinic Location & Mailing Address
                    </p>
                    <span className="text-[10px] text-on-surface-variant">Spoken to patients for clinic directions</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="sm:col-span-2">
                      <label className="overline text-[10px] block mb-1">Street Address *</label>
                      <input
                        type="text"
                        value={address}
                        onChange={(e) => setAddress(e.target.value)}
                        placeholder="e.g. 100 Michigan Avenue"
                        className="input-field text-xs"
                      />
                    </div>
                    <div>
                      <label className="overline text-[10px] block mb-1">Suite / Unit / Floor</label>
                      <input
                        type="text"
                        value={suite}
                        onChange={(e) => setSuite(e.target.value)}
                        placeholder="e.g. Suite 400"
                        className="input-field text-xs"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="overline text-[10px] block mb-1">City / Municipality *</label>
                      <input
                        type="text"
                        value={city}
                        maxLength={100}
                        onChange={(e) => {
                          setCity(e.target.value);
                          if (profileErrors.city) setProfileErrors(prev => ({ ...prev, city: null }));
                        }}
                        className={`input-field text-xs ${profileErrors.city ? "border-rose-500 ring-1 ring-rose-500/30" : ""}`}
                        placeholder="e.g. Chicago"
                        required
                      />
                      {profileErrors.city && (
                        <p className="text-[10px] text-rose-500 font-medium mt-1 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> {profileErrors.city}
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="overline text-[10px] block mb-1">State / Province</label>
                      <input
                        type="text"
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                        placeholder="e.g. IL"
                        className="input-field text-xs uppercase"
                        maxLength={10}
                      />
                    </div>
                    <div>
                      <label className="overline text-[10px] block mb-1">Zip / Postal Code</label>
                      <input
                        type="text"
                        value={zipCode}
                        onChange={(e) => setZipCode(e.target.value)}
                        placeholder="e.g. 60601"
                        className="input-field text-xs font-mono"
                        maxLength={12}
                      />
                    </div>
                  </div>
                </div>

                {/* Field 4 & 5: Timezone & Owner Email */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="overline mb-1.5 block">Primary Timezone</label>
                    <select
                      value={timezone}
                      onChange={(e) => {
                        setTimezone(e.target.value);
                        if (profileErrors.timezone) setProfileErrors(prev => ({ ...prev, timezone: null }));
                      }}
                      className="input-field appearance-none cursor-pointer"
                    >
                      {US_TIMEZONES.map(tz => (
                        <option key={tz.value} value={tz.value}>{tz.label}</option>
                      ))}
                      {timezone && !US_TIMEZONES.some(tz => tz.value === timezone) && (
                        <option value={timezone}>{timezone}</option>
                      )}
                    </select>
                    <p className="text-[11px] text-on-surface-variant mt-1">AI voice receptionist uses this timezone for calendar bookings and slot calculations.</p>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="overline">Owner / Admin Email *</label>
                      <span className="text-[10px] text-on-surface-variant/70 font-mono">Primary Login</span>
                    </div>
                    <div className={`flex items-center gap-2 input-field bg-surface-container-highest transition-colors ${
                      profileErrors.ownerEmail ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                    }`}>
                      <Mail className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                      <input
                        type="email"
                        value={ownerEmail}
                        onChange={(e) => {
                          setOwnerEmail(e.target.value);
                          if (profileErrors.ownerEmail) setProfileErrors(prev => ({ ...prev, ownerEmail: null }));
                        }}
                        className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface font-mono"
                        placeholder="e.g. admin@sunriseclinic.com"
                        required
                      />
                    </div>
                    {profileErrors.ownerEmail && (
                      <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" /> {profileErrors.ownerEmail}
                      </p>
                    )}
                    <p className="text-[11px] text-on-surface-variant mt-1">Primary administrative login, escalation contact, and security alert recipient.</p>
                  </div>
                </div>

                {/* Field 6: Patient Direct Phone Line */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <label className="overline">Patient Direct Phone (Assigned Line)</label>
                    <span className="text-[10px] text-on-surface-variant/70 font-mono">Voice & SMS Inbound</span>
                  </div>
                  <div className={`flex items-center gap-2 input-field bg-surface-container-highest transition-colors ${
                    profileErrors.phoneNumber ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                  }`}>
                    <Phone className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="text"
                      value={phoneNumber}
                      onChange={(e) => {
                        setPhoneNumber(e.target.value);
                        if (profileErrors.phoneNumber) setProfileErrors(prev => ({ ...prev, phoneNumber: null }));
                      }}
                      className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface font-mono"
                      placeholder="e.g. +1 (555) 123-4567"
                    />
                  </div>
                  {profileErrors.phoneNumber && (
                    <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {profileErrors.phoneNumber}
                    </p>
                  )}
                  <p className="text-[11px] text-on-surface-variant mt-1">Primary incoming phone line for patient calls, AI voice receptionist routing, and automated SMS reminders.</p>
                </div>
              </div>

              <div className="pt-4 border-t border-surface-container flex items-center justify-between">
                <span className="text-xs text-on-surface-variant">Changes persist instantly to the PostgreSQL database on save.</span>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn-primary flex items-center gap-2"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  <span>{saving ? "Saving Changes..." : "Save Clinic Profile"}</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: DOCTOR INFO */}
          {activeTab === "doctor" && (
            <div className="space-y-6">
              <div className="border-b border-surface-container pb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                      <User className="w-5 h-5 text-primary" />
                      {t.doctor_full_name ? "Primary Doctor & Clinician Profile" : "Primary Doctor Information"}
                    </h3>
                    <p className="text-xs text-on-surface-variant mt-1">
                      {t.doctor_info_sub || "Clinician credentials, NPI, and state license for AI voice prompts and EHR billing verification."}
                    </p>
                  </div>
                  <span className="text-[11px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-md bg-primary/10 text-primary border border-primary/20">
                    Voice & EHR Synced
                  </span>
                </div>
              </div>

              {/* Info & Compliance Banner */}
              <div className="p-3.5 bg-surface-container-low rounded-xl border border-surface-container flex items-start gap-3">
                <Info className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                <div className="text-xs text-on-surface-variant leading-relaxed">
                  <span className="font-semibold text-on-surface">Voice AI & Billing Injection:</span> The Primary Doctor's name and credentials are dynamically injected into your CALL-E AI Voice Agent greeting and campaign prompts. The NPI number and state medical license are mapped to EHR claims and clearinghouse billing exports.
                </div>
              </div>

              <div className="space-y-5">
                {/* Field 1: Doctor Full Name */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="overline">Doctor Full Name</p>
                    <span className="text-[10px] text-on-surface-variant/70 font-mono">Max 120 chars</span>
                  </div>
                  <div className={`flex gap-2.5 items-center input-field bg-surface-container-highest transition-colors ${
                    doctorErrors.doctorName ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                  }`}>
                    <User className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="text"
                      value={doctorName}
                      onChange={(e) => {
                        setDoctorName(e.target.value);
                        if (doctorErrors.doctorName) {
                          setDoctorErrors(prev => ({ ...prev, doctorName: null }));
                        }
                      }}
                      maxLength={120}
                      className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface placeholder:text-on-surface-variant/40"
                      placeholder="e.g. Dr. Hamza Nasiem"
                    />
                  </div>
                  {doctorErrors.doctorName && (
                    <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {doctorErrors.doctorName}
                    </p>
                  )}
                  <p className="text-[11px] text-on-surface-variant/70 mt-1">
                    Formal name introduced by AI Voice Receptionist when patients call the clinic.
                  </p>
                </div>

                {/* Field 2: Doctor Credentials & Degrees */}
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <p className="overline">Doctor Credentials & Degrees</p>
                    <span className="text-[10px] text-on-surface-variant/70">Click to toggle quick badges</span>
                  </div>

                  {/* Preset Pills / Badges */}
                  <div className="flex flex-wrap gap-1.5 mb-2.5">
                    {CREDENTIAL_PRESETS.map(cred => {
                      const active = doctorCredentials
                        ? doctorCredentials.split(",").map(c => c.trim().toLowerCase()).includes(cred.toLowerCase())
                        : false;
                      return (
                        <button
                          key={cred}
                          type="button"
                          onClick={() => toggleCredential(cred)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                            active
                              ? "bg-primary text-white shadow-sm ring-1 ring-primary/40 scale-[1.02]"
                              : "bg-surface-container hover:bg-surface-container-high text-on-surface-variant border border-surface-container"
                          }`}
                        >
                          {cred} {active && "✓"}
                        </button>
                      );
                    })}
                  </div>

                  <div className={`flex gap-2.5 items-center input-field bg-surface-container-highest transition-colors ${
                    doctorErrors.doctorCredentials ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                  }`}>
                    <Award className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="text"
                      value={doctorCredentials}
                      onChange={(e) => {
                        setDoctorCredentials(e.target.value);
                        if (doctorErrors.doctorCredentials) {
                          setDoctorErrors(prev => ({ ...prev, doctorCredentials: null }));
                        }
                      }}
                      maxLength={60}
                      className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface placeholder:text-on-surface-variant/40"
                      placeholder="e.g. PT, DPT, OCS (Doctor of Physical Therapy)"
                    />
                  </div>
                  {doctorErrors.doctorCredentials && (
                    <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {doctorErrors.doctorCredentials}
                    </p>
                  )}
                  <p className="text-[11px] text-on-surface-variant/70 mt-1">
                    Select preset badges above or enter custom clinical designations (MD, DO, PT, DPT, DC, DDS, etc.).
                  </p>
                </div>

                {/* Field 3: Doctor Direct Phone / Backline */}
                <div>
                  <p className="overline mb-1.5">Doctor Direct Phone / Clinic Backline</p>
                  <div className={`flex gap-2.5 items-center input-field bg-surface-container-highest transition-colors ${
                    doctorErrors.doctorPhone ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                  }`}>
                    <Phone className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="text"
                      value={doctorPhone}
                      onChange={(e) => {
                        setDoctorPhone(e.target.value);
                        if (doctorErrors.doctorPhone) {
                          setDoctorErrors(prev => ({ ...prev, doctorPhone: null }));
                        }
                      }}
                      className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface font-mono placeholder:text-on-surface-variant/40"
                      placeholder="e.g. +1 (555) 999-8888"
                    />
                  </div>
                  {doctorErrors.doctorPhone && (
                    <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> {doctorErrors.doctorPhone}
                    </p>
                  )}
                  <p className="text-[11px] text-on-surface-variant/70 mt-1">
                    Direct provider contact for priority provider-to-provider communications and emergency routing.
                  </p>
                </div>

                {/* Field 4 & 5 Grid: NPI Number & Medical License */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
                  {/* NPI Number */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <p className="overline">National Provider Identifier (NPI)</p>
                      {npiNumber.length === 10 ? (
                        <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                          ✓ 10-Digit Valid
                        </span>
                      ) : (
                        <span className="text-[10px] text-on-surface-variant/70 font-mono">
                          {npiNumber.length}/10 digits
                        </span>
                      )}
                    </div>
                    <div className={`flex gap-2.5 items-center input-field bg-surface-container-highest transition-colors ${
                      doctorErrors.npiNumber ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                    }`}>
                      <Hash className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                      <input
                        type="text"
                        value={npiNumber}
                        onChange={(e) => handleNpiChange(e.target.value)}
                        maxLength={10}
                        inputMode="numeric"
                        className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface font-mono tracking-wider placeholder:text-on-surface-variant/40"
                        placeholder="e.g. 1234567890"
                      />
                    </div>
                    {doctorErrors.npiNumber && (
                      <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" /> {doctorErrors.npiNumber}
                      </p>
                    )}
                    <p className="text-[11px] text-on-surface-variant/70 mt-1">
                      10-digit CMS unique healthcare identifier for billing claims and HIPAA compliance.
                    </p>
                  </div>

                  {/* State Medical License */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <p className="overline">State Medical License Number</p>
                      <span className="text-[10px] text-on-surface-variant/70 font-mono">State Board ID</span>
                    </div>
                    <div className={`flex gap-2.5 items-center input-field bg-surface-container-highest transition-colors ${
                      doctorErrors.medicalLicense ? "border border-rose-500 ring-1 ring-rose-500/30" : ""
                    }`}>
                      <ShieldCheck className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                      <input
                        type="text"
                        value={medicalLicense}
                        onChange={(e) => handleLicenseChange(e.target.value)}
                        maxLength={50}
                        className="flex-1 bg-transparent outline-none border-none text-sm text-on-surface font-mono uppercase placeholder:text-on-surface-variant/40"
                        placeholder="e.g. PT-048291 or MD-982314"
                      />
                    </div>
                    {doctorErrors.medicalLicense && (
                      <p className="text-xs text-rose-500 font-medium mt-1 flex items-center gap-1">
                        <AlertCircle className="w-3.5 h-3.5" /> {doctorErrors.medicalLicense}
                      </p>
                    )}
                    <p className="text-[11px] text-on-surface-variant/70 mt-1">
                      State medical licensing board practitioner registry identifier.
                    </p>
                  </div>
                </div>

                {/* Doctor Tab Save Bar */}
                <div className="pt-4 border-t border-surface-container flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <span className="text-xs text-on-surface-variant">
                    Doctor credentials, NPI, and license sync directly to Voice AI prompts, call routing, and EHR billing records.
                  </span>
                  <button
                    onClick={handleSave}
                    disabled={saving}
                    className="btn-primary flex items-center gap-2 self-start sm:self-auto"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    <span>{saving ? "Saving Changes..." : "Save Doctor Profile"}</span>
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB: TEAM & STAFF */}
          {activeTab === "team" && isOwner && (
            <TeamSettings />
          )}

          {/* TAB 3: BUSINESS HOURS & PROTOCOLS */}
          {activeTab === "hours" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-container pb-4">
                <div>
                  <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                    <Clock className="w-5 h-5 text-primary" /> Business Hours & Emergency Protocols
                  </h3>
                  <p className="text-xs text-on-surface-variant mt-1">
                    Define weekly operating schedules, medical triage guardrails, and live human receptionist escalation line.
                  </p>
                </div>
                <div className="flex items-center gap-2 flex-wrap justify-end">
                  <button
                    type="button"
                    onClick={handleApplyStandardMedicalPreset}
                    className="px-2.5 py-1.5 rounded-lg text-[11px] font-bold bg-primary/10 hover:bg-primary/20 text-primary border border-primary/30 transition-colors flex items-center gap-1.5"
                    title="Mon-Fri 8:00 AM - 5:00 PM, Sat 9:00 AM - 1:00 PM, Sun Closed"
                  >
                    <Sparkles className="w-3.5 h-3.5" />
                    <span>Mon–Fri 8am–5pm, Sat 9am–1pm (Standard)</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleCopyMonToWeekdays}
                    className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-surface-container hover:bg-surface-container-highest text-on-surface transition-colors flex items-center gap-1.5"
                    title="Copy Monday's schedule to Tuesday through Friday"
                  >
                    <Copy className="w-3.5 h-3.5 text-primary" />
                    <span>Copy Mon to Mon–Fri</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleApplyPreset("08:00", "18:00", false)}
                    className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-surface-container hover:bg-surface-container-highest text-on-surface transition-colors"
                  >
                    8am – 6pm (Mon–Fri)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleApplyPreset("09:00", "17:00", false)}
                    className="px-2.5 py-1.5 rounded-lg text-[11px] font-semibold bg-surface-container hover:bg-surface-container-highest text-on-surface transition-colors"
                  >
                    9am – 5pm (Mon–Fri)
                  </button>
                </div>
              </div>

              {/* Schedule Grid */}
              <div className="space-y-3">
                {DAYS_CONFIG.map(({ key, label }) => {
                  const d = hours[key] || DEFAULT_HOURS[key];
                  const isInvalidRange = d.enabled && d.start >= d.end;

                  return (
                    <div
                      key={key}
                      className={`flex items-start sm:items-center gap-3 p-3 rounded-xl border transition-all ${
                        d.enabled
                          ? "bg-surface-container-low border-surface-container"
                          : "bg-surface-container-lowest border-surface-container/60 opacity-80"
                      }`}
                    >
                      {/* Day Name & Toggle */}
                      <div className="flex items-center gap-3 w-32 sm:w-40 flex-shrink-0">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={Boolean(d.enabled)}
                            onChange={(e) => handleHourChange(key, "enabled", e.target.checked)}
                            className="sr-only peer"
                          />
                          <div className="w-10 h-5 bg-surface-container-highest rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                        </label>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-semibold text-on-surface">{label}</span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              d.enabled
                                ? "bg-[#edf7e0] text-[#396a00]"
                                : "bg-surface-container text-on-surface-variant"
                            }`}
                          >
                            {d.enabled ? "Open" : "Closed"}
                          </span>
                        </div>
                      </div>

                      {/* Controls / State */}
                      {d.enabled ? (
                        <div className="flex flex-wrap items-center gap-2 flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-on-surface-variant">Start:</span>
                            <select
                              value={d.start}
                              onChange={(e) => handleHourChange(key, "start", e.target.value)}
                              className="px-2 py-1 bg-surface-container-highest text-on-surface rounded-lg text-[11px] font-semibold outline-none border border-surface-container focus:border-primary cursor-pointer font-mono"
                            >
                              {getTimeOptions(d.start).map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <span className="text-xs text-on-surface-variant font-medium">to</span>

                          <div className="flex items-center gap-2">
                            <span className="text-xs text-on-surface-variant">End:</span>
                            <select
                              value={d.end}
                              onChange={(e) => handleHourChange(key, "end", e.target.value)}
                              className="px-2 py-1 bg-surface-container-highest text-on-surface rounded-lg text-[11px] font-semibold outline-none border border-surface-container focus:border-primary cursor-pointer font-mono"
                            >
                              {getTimeOptions(d.end).map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                  {opt.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          {isInvalidRange && (
                            <span className="text-[11px] font-semibold text-rose-500 flex items-center gap-1">
                              <AlertCircle className="w-3.5 h-3.5" />
                              End time must be after start time
                            </span>
                          )}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 py-1 flex-1 min-w-0">
                          <span className="text-[11px] text-on-surface-variant italic truncate">
                            Closed — AI voice receptionist declines booking requests for this day.
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Emergency Medical Protocols & Call Transfer Card */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container-high/60 space-y-4">
                <div className="flex items-center justify-between border-b border-surface-container pb-3">
                  <div className="flex items-center gap-2">
                    <ShieldAlert className="w-4.5 h-4.5 text-amber-500" />
                    <div>
                      <h4 className="text-sm font-bold text-on-surface">Emergency Medical Protocols & Call Transfer</h4>
                      <p className="text-xs text-on-surface-variant">Critical safety triage directives and human front-desk escalation routing.</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-bold text-amber-600 dark:text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 rounded-full">
                    Chest Pain / 911 Safety Rule
                  </span>
                </div>

                <div className="space-y-3.5">
                  <div>
                    <label className="overline text-[11px] block mb-1.5">
                      Emergency Medical Protocol Instructions (Spoken Immediately for High-Risk Symptoms) *
                    </label>
                    <textarea
                      value={emergencyProtocols}
                      onChange={(e) => setEmergencyProtocols(e.target.value)}
                      placeholder="If caller reports chest pain, severe shortness of breath, sudden weakness, numbness, or life-threatening symptoms, immediately direct them to hang up and call 911 or proceed to the nearest emergency department."
                      className="input-field text-xs min-h-[75px] resize-y text-on-surface leading-relaxed"
                    />
                    <p className="text-[11px] text-on-surface-variant mt-1">
                      Injected into the core LLM voice prompt. The AI will interrupt scheduling and instruct the caller to dial 911 when emergency symptoms are detected.
                    </p>
                  </div>

                  <div>
                    <label className="overline text-[11px] block mb-1.5">
                      Live Call Transfer Phone Number (Human Front-Desk Escalation)
                    </label>
                    <div className="flex gap-2 items-center input-field bg-surface-container-highest max-w-md">
                      <Phone className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                      <input
                        type="text"
                        value={transferPhoneNumber}
                        onChange={(e) => setTransferPhoneNumber(e.target.value)}
                        className="flex-1 bg-transparent outline-none border-none text-xs text-on-surface font-mono"
                        placeholder="e.g. +1 (555) 987-6543"
                      />
                    </div>
                    <p className="text-[11px] text-on-surface-variant mt-1">
                      When callers request human assistance or encounter complex inquiries, the AI executes a live telephony transfer to this number.
                    </p>
                  </div>
                </div>
              </div>

              {/* Business Hours & Protocols Save Bar */}
              <div className="pt-4 border-t border-surface-container flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <span className="text-xs text-on-surface-variant">
                  Weekly schedule and emergency escalation rules persist to PostgreSQL and sync to CALL-E engine.
                </span>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn-primary flex items-center gap-2 self-start sm:self-auto"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                  <span>{saving ? "Saving Changes..." : "Save Business Hours & Protocols"}</span>
                </button>
              </div>
            </div>
          )}

          {/* TAB 4: APPOINTMENT TYPES */}
          {activeTab === "types" && (
            <div className="space-y-6">
              <div className="border-b border-surface-container pb-4">
                <h3 className="text-base font-bold text-on-surface">Appointment Types</h3>
                <p className="text-xs text-on-surface-variant mt-1">Configure appointment types, duration in minutes, and service fees. AI Receptionist books patients, syncs calendar slots, and quotes pricing using these settings.</p>
              </div>

              {/* Add Type Form */}
              <div className="bg-surface-container rounded-[0.75rem] p-4 space-y-3">
                <p className="overline text-xs">Add New Type</p>
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                  <div className="sm:col-span-6">
                    <input
                      type="text"
                      value={newTypeName}
                      onChange={(e) => setNewTypeName(e.target.value)}
                      placeholder="e.g. Initial Evaluation / Deep Tissue"
                      className="input-field w-full"
                    />
                  </div>
                  <div className="sm:col-span-3 flex items-center gap-2 bg-surface-container-highest rounded-[0.75rem] px-3 py-1 text-sm text-on-surface">
                    <Clock className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="number"
                      min="5"
                      step="5"
                      value={newTypeDuration}
                      onChange={(e) => setNewTypeDuration(parseInt(e.target.value) || 0)}
                      placeholder="Minutes"
                      className="w-full bg-transparent outline-none text-sm font-semibold"
                    />
                    <span className="text-xs text-on-surface-variant whitespace-nowrap">min</span>
                  </div>
                  <div className="sm:col-span-3 flex items-center gap-2 bg-surface-container-highest rounded-[0.75rem] px-3 py-1 text-sm text-on-surface">
                    <DollarSign className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="number"
                      min="0"
                      step="1"
                      value={newTypeFee}
                      onChange={(e) => setNewTypeFee(parseFloat(e.target.value) || 0)}
                      placeholder="Fee ($)"
                      className="w-full bg-transparent outline-none text-sm font-semibold"
                    />
                    <span className="text-xs text-on-surface-variant whitespace-nowrap">USD</span>
                  </div>
                </div>
                <div className="flex justify-end pt-1">
                  <button
                    onClick={handleAddApptType}
                    disabled={!newTypeName.trim()}
                    className="btn-primary py-2 px-5 flex items-center justify-center gap-2 text-xs font-bold"
                  >
                    <Plus className="w-4 h-4" /> Add Appointment Type
                  </button>
                </div>
              </div>

              {/* Types List */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <p className="overline">Active Appointment Types ({apptTypes.length})</p>
                  <span className="text-xs text-on-surface-variant">Syncs live with voice booking & calendar</span>
                </div>
                
                {apptTypes.length === 0 ? (
                  <div className="text-center py-8 text-sm text-on-surface-variant bg-surface-container-low rounded-xl border border-dashed border-surface-container">
                    No active appointment types configured. Add one above.
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-2.5">
                    {apptTypes.map((type, idx) => {
                      const dur = type.duration_minutes || type.duration || 30;
                      const fee = type.fee !== undefined ? type.fee : (type.price !== undefined ? type.price : 0);
                      const isEditing = editingApptIdx === idx;

                      if (isEditing) {
                        return (
                          <div key={idx} className="bg-surface-container p-4 rounded-xl border border-primary/50 shadow-sm space-y-3 animate-in fade-in duration-150">
                            <div className="grid grid-cols-1 sm:grid-cols-12 gap-3">
                              <div className="sm:col-span-6">
                                <label className="text-[11px] font-bold text-on-surface-variant block mb-1">Type Name</label>
                                <input
                                  type="text"
                                  value={editingAppt.name}
                                  onChange={(e) => setEditingAppt({ ...editingAppt, name: e.target.value })}
                                  className="input-field w-full text-xs py-1.5"
                                  autoFocus
                                />
                              </div>
                              <div className="sm:col-span-3">
                                <label className="text-[11px] font-bold text-on-surface-variant block mb-1">Duration (min)</label>
                                <div className="flex items-center gap-2 bg-surface-container-highest rounded-[0.75rem] px-3 py-1 text-sm text-on-surface">
                                  <Clock className="w-3.5 h-3.5 text-on-surface-variant flex-shrink-0" />
                                  <input
                                    type="number"
                                    min="5"
                                    step="5"
                                    value={editingAppt.duration_minutes || editingAppt.duration || 30}
                                    onChange={(e) => setEditingAppt({ ...editingAppt, duration: parseInt(e.target.value) || 5, duration_minutes: parseInt(e.target.value) || 5 })}
                                    className="w-full bg-transparent outline-none text-xs font-semibold"
                                  />
                                </div>
                              </div>
                              <div className="sm:col-span-3">
                                <label className="text-[11px] font-bold text-on-surface-variant block mb-1">Fee ($)</label>
                                <div className="flex items-center gap-2 bg-surface-container-highest rounded-[0.75rem] px-3 py-1 text-sm text-on-surface">
                                  <DollarSign className="w-3.5 h-3.5 text-on-surface-variant flex-shrink-0" />
                                  <input
                                    type="number"
                                    min="0"
                                    step="1"
                                    value={editingAppt.fee !== undefined ? editingAppt.fee : (editingAppt.price || 0)}
                                    onChange={(e) => setEditingAppt({ ...editingAppt, fee: parseFloat(e.target.value) || 0 })}
                                    className="w-full bg-transparent outline-none text-xs font-semibold"
                                  />
                                </div>
                              </div>
                            </div>
                            <div className="flex items-center justify-end gap-2 pt-1">
                              <button
                                onClick={handleCancelEditApptType}
                                className="px-3 py-1.5 rounded-lg border border-surface-container text-xs font-semibold text-on-surface hover:bg-surface-container-highest transition-colors"
                              >
                                Cancel
                              </button>
                              <button
                                onClick={handleSaveEditApptType}
                                className="btn-primary py-1.5 px-4 text-xs flex items-center gap-1.5"
                              >
                                <Check className="w-3.5 h-3.5" /> Apply
                              </button>
                            </div>
                          </div>
                        );
                      }

                      return (
                        <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-surface-container-low px-4 py-3 rounded-xl border border-surface-container transition-all hover:border-surface-container-highest">
                          <div className="flex items-center gap-3">
                            <div className="w-2.5 h-2.5 rounded-full bg-primary flex-shrink-0" />
                            <span className="text-sm font-bold text-on-surface">{type.name}</span>
                          </div>
                          <div className="flex items-center gap-2.5 self-end sm:self-auto">
                            <span className="text-xs font-semibold px-3 py-1 bg-surface-container-highest text-on-surface-variant rounded-full flex items-center gap-1.5">
                              <Clock className="w-3.5 h-3.5 text-on-surface-variant" />
                              {dur} mins
                            </span>
                            <span className="text-xs font-semibold px-3 py-1 bg-[#edf7e0] text-[#396a00] rounded-full flex items-center gap-1">
                              <DollarSign className="w-3.5 h-3.5 text-[#396a00]" />
                              ${fee}
                            </span>
                            <button
                              onClick={() => handleStartEditApptType(idx)}
                              className="p-1.5 text-on-surface-variant hover:text-primary rounded-lg transition-colors"
                              title="Edit appointment type"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleRemoveApptType(idx)}
                              disabled={apptTypes.length <= 1}
                              className="p-1.5 text-on-surface-variant hover:text-rose-500 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg transition-colors"
                              title={apptTypes.length <= 1 ? "At least one appointment type is required" : "Delete Type"}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 5: INTEGRATIONS */}
          {activeTab === "integrations" && (
            <div className="space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-surface-container pb-4">
                <div>
                  <h3 className="text-base font-bold text-on-surface">Third Party Integrations</h3>
                  <p className="text-xs text-on-surface-variant mt-1">Manage live connections for your calendar, telephony, voice AI engine, and billing systems.</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={fetchIntegrationsStatus}
                    disabled={loadingIntegrations}
                    className="px-3 py-1.5 rounded-lg border border-surface-container text-xs font-semibold text-on-surface hover:bg-surface-container flex items-center gap-1.5 transition-colors"
                    title="Refresh live status"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${loadingIntegrations ? "animate-spin text-primary" : ""}`} />
                    <span>Refresh</span>
                  </button>
                  <button
                    onClick={handleSaveIntegrations}
                    disabled={savingIntegrations}
                    className="btn-primary py-1.5 px-3 text-xs flex items-center gap-1.5"
                  >
                    {savingIntegrations ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    <span>Save Integrations</span>
                  </button>
                </div>
              </div>

              {/* INTEGRATION 1: GOOGLE CALENDAR OAUTH */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start sm:items-center gap-3.5">
                    <div className="w-11 h-11 bg-[#e8f0fe] rounded-xl flex items-center justify-center flex-shrink-0 border border-[#d2e3fc]">
                      <Calendar className="w-6 h-6 text-[#1a73e8]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Google Calendar 2-Way Sync</h4>
                        {isGoogleConnected ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#edf7e0] text-[#396a00] border border-[#d4edba]">
                            <CheckCircle2 className="w-3 h-3" /> Connected
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                            <AlertCircle className="w-3 h-3" /> Disconnected
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Automated two-way appointment calendar sync, double-booking prevention, and real-time doctor availability check.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    {isGoogleConnected ? (
                      <>
                        <button
                          onClick={() => handleTestIntegration('google')}
                          disabled={testingService === 'google'}
                          className="px-3 py-1.5 rounded-lg border border-surface-container-highest bg-surface-container-high hover:bg-surface-container-highest text-xs font-semibold text-on-surface flex items-center gap-1.5 transition-colors"
                        >
                          {testingService === 'google' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
                          <span>Test Sync</span>
                        </button>
                        <button
                          onClick={connectGoogle}
                          className="px-3 py-1.5 rounded-lg border border-surface-container bg-surface-container hover:bg-surface-container-high text-xs font-semibold text-on-surface flex items-center gap-1.5 transition-colors"
                        >
                          <RefreshCw className="w-3.5 h-3.5" /> Reconnect
                        </button>
                        <button
                          onClick={handleDisconnectGoogle}
                          disabled={disconnectingGoogle}
                          className="px-3 py-1.5 rounded-lg border border-rose-200 text-rose-600 hover:bg-rose-50 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                        >
                          {disconnectingGoogle ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Unlink className="w-3.5 h-3.5" />}
                          <span>Disconnect</span>
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={connectGoogle}
                        className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#1a73e8] hover:bg-[#1557b0] shadow-sm flex items-center gap-2 transition-all active:scale-[0.98]"
                      >
                        <Calendar className="w-4 h-4" />
                        <span>Connect Google Calendar</span>
                      </button>
                    )}
                  </div>
                </div>

                {/* Inline Test Result Banner */}
                {testResult && testResult.service === 'google' && (
                  <div className={`p-3 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-1 ${
                    testResult.success ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]" : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
                  }`}>
                    <div className="flex items-center gap-2">
                      {testResult.success ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />}
                      <span>{testResult.message}</span>
                    </div>
                    <button onClick={() => setTestResult(null)} className="opacity-70 hover:opacity-100 font-bold px-1.5 py-0.5">✕</button>
                  </div>
                )}

                {isGoogleConnected && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 border-t border-surface-container-high/60">
                    <div>
                      <label className="overline mb-1 block">Active Google Calendar ID</label>
                      <input
                        type="text"
                        value={googleCalendarId}
                        onChange={(e) => setGoogleCalendarId(e.target.value)}
                        placeholder="primary"
                        className="input-field font-mono text-xs"
                      />
                    </div>
                    <div>
                      <label className="overline mb-1 block">OAuth Authorization Status</label>
                      <div className="px-3 py-2 bg-surface-container-high rounded-xl text-xs font-medium text-on-surface flex items-center justify-between">
                        <span className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-[#396a00]" />
                          <span>OAuth 2.0 Token (Offline Access Active)</span>
                        </span>
                        <span className="text-[10px] text-on-surface-variant font-mono">Scope: calendar</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* INTEGRATION 2: TELNYX TELEPHONY LINE */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start sm:items-center gap-3.5">
                    <div className="w-11 h-11 bg-[#e3f2fd] rounded-xl flex items-center justify-center flex-shrink-0 border border-[#bbdefb]">
                      <Phone className="w-6 h-6 text-[#006493]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Telnyx Assistant Phone Line</h4>
                        {isTelnyxConnected ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#edf7e0] text-[#396a00] border border-[#d4edba]">
                            <CheckCircle2 className="w-3 h-3" /> Live Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                            <AlertCircle className="w-3 h-3" /> Unassigned
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Dedicated telecommunications line assigned to your AI receptionist for inbound calls and direct SMS routing.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <button
                      onClick={() => handleTestIntegration('telnyx')}
                      disabled={testingService === 'telnyx'}
                      className="px-3 py-1.5 rounded-lg border border-surface-container-highest bg-surface-container-high hover:bg-surface-container-highest text-xs font-semibold text-on-surface flex items-center gap-1.5 transition-colors"
                    >
                      {testingService === 'telnyx' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
                      <span>Test Line</span>
                    </button>
                  </div>
                </div>

                {/* Inline Test Result Banner */}
                {testResult && testResult.service === 'telnyx' && (
                  <div className={`p-3 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-1 ${
                    testResult.success ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]" : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
                  }`}>
                    <div className="flex items-center gap-2">
                      {testResult.success ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />}
                      <span>{testResult.message}</span>
                    </div>
                    <button onClick={() => setTestResult(null)} className="opacity-70 hover:opacity-100 font-bold px-1.5 py-0.5">✕</button>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-surface-container-high/60">
                  <div>
                    <label className="overline mb-1.5 block">Telnyx Phone Number (E.164 with Country Code) *</label>
                    <input
                      type="text"
                      value={telnyxNumber}
                      onChange={(e) => setTelnyxNumber(e.target.value)}
                      placeholder="e.g. +15755734355"
                      className="input-field font-mono text-sm"
                    />
                    <p className="text-[11px] text-on-surface-variant mt-1">Must include country code (e.g. +1 for US/Canada).</p>
                  </div>

                  <div>
                    <label className="overline mb-1.5 block">Telnyx Inbound SMS Webhook URL</label>
                    <div className="flex items-center gap-2 bg-surface-container-high rounded-xl px-3 py-2">
                      <code className="text-xs text-on-surface flex-1 font-mono truncate">{telnyxWebhookUrl}</code>
                      <button
                        onClick={() => handleCopy(telnyxWebhookUrl, "telnyx_webhook")}
                        className="text-on-surface-variant hover:text-primary transition-colors flex-shrink-0 p-1"
                        title="Copy Webhook URL"
                      >
                        {copiedKey === "telnyx_webhook" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <p className="text-[11px] text-on-surface-variant mt-1">Paste into your Telnyx Portal → Messaging Profile Webhooks.</p>
                  </div>
                </div>
              </div>

              {/* INTEGRATION 3: TWILIO SMS & TELEPHONY */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start sm:items-center gap-3.5">
                    <div className="w-11 h-11 bg-[#fee2e2] rounded-xl flex items-center justify-center flex-shrink-0 border border-[#fecaca]">
                      <MessageSquare className="w-6 h-6 text-[#b91c1c]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Twilio SMS & Messaging Pipeline</h4>
                        {isTwilioConnected ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#edf7e0] text-[#396a00] border border-[#d4edba]">
                            <CheckCircle2 className="w-3 h-3" /> System Connected
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                            <AlertCircle className="w-3 h-3" /> Standby
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        High-throughput carrier routing for automated appointment reminders, 2-way patient SMS confirmations, and recall campaigns.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <button
                      onClick={() => handleTestIntegration('twilio')}
                      disabled={testingService === 'twilio'}
                      className="px-3 py-1.5 rounded-lg border border-surface-container-highest bg-surface-container-high hover:bg-surface-container-highest text-xs font-semibold text-on-surface flex items-center gap-1.5 transition-colors"
                    >
                      {testingService === 'twilio' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
                      <span>Test Twilio</span>
                    </button>
                  </div>
                </div>

                {/* Inline Test Result Banner */}
                {testResult && testResult.service === 'twilio' && (
                  <div className={`p-3 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-1 ${
                    testResult.success ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]" : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
                  }`}>
                    <div className="flex items-center gap-2">
                      {testResult.success ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />}
                      <span>{testResult.message}</span>
                    </div>
                    <button onClick={() => setTestResult(null)} className="opacity-70 hover:opacity-100 font-bold px-1.5 py-0.5">✕</button>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-surface-container-high/60">
                  <div>
                    <label className="overline mb-1.5 block">Twilio Assigned Phone Number</label>
                    <input
                      type="text"
                      value={twilioNumber}
                      onChange={(e) => setTwilioNumber(e.target.value)}
                      placeholder="e.g. +15551234567"
                      className="input-field font-mono text-sm"
                    />
                    <p className="text-[11px] text-on-surface-variant mt-1">Sender number for automated reminders and recall dispatch.</p>
                  </div>

                  <div>
                    <label className="overline mb-1.5 block">Twilio Inbound SMS Webhook URL</label>
                    <div className="flex items-center gap-2 bg-surface-container-high rounded-xl px-3 py-2">
                      <code className="text-xs text-on-surface flex-1 font-mono truncate">{twilioSmsWebhookUrl}</code>
                      <button
                        onClick={() => handleCopy(twilioSmsWebhookUrl, "twilio_sms_webhook")}
                        className="text-on-surface-variant hover:text-primary transition-colors flex-shrink-0 p-1"
                        title="Copy Webhook URL"
                      >
                        {copiedKey === "twilio_sms_webhook" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <p className="text-[11px] text-on-surface-variant mt-1">Configured in Twilio Console → Phone Numbers → Webhooks.</p>
                  </div>
                </div>
              </div>

              {/* INTEGRATION 4: CALL-E AI VOICE ENGINE */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start sm:items-center gap-3.5">
                    <div className="w-11 h-11 bg-primary-container/30 rounded-xl flex items-center justify-center flex-shrink-0 border border-primary/20">
                      <Bot className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">CALL-E AI Phone Engine</h4>
                        {isCalleConnected ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#edf7e0] text-[#396a00] border border-[#d4edba]">
                            <CheckCircle2 className="w-3 h-3" /> iams_live_018f7d9a (Active)
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                            <AlertCircle className="w-3 h-3" /> Configured
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Autonomous phone agent for appointment confirmations, 30/60/90-day recalls, and no-show follow-ups.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <button
                      onClick={() => handleTestIntegration('calle')}
                      disabled={testingService === 'calle'}
                      className="px-3 py-1.5 rounded-lg border border-surface-container-highest bg-surface-container-high hover:bg-surface-container-highest text-xs font-semibold text-on-surface flex items-center gap-1.5 transition-colors"
                    >
                      {testingService === 'calle' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
                      <span>Test CALL-E</span>
                    </button>
                  </div>
                </div>

                {/* Inline Test Result Banner */}
                {testResult && testResult.service === 'calle' && (
                  <div className={`p-3 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-1 ${
                    testResult.success ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]" : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
                  }`}>
                    <div className="flex items-center gap-2">
                      {testResult.success ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />}
                      <span>{testResult.message}</span>
                    </div>
                    <button onClick={() => setTestResult(null)} className="opacity-70 hover:opacity-100 font-bold px-1.5 py-0.5">✕</button>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-surface-container-high/60">
                  <div>
                    <label className="overline mb-1.5 block">CALL-E Engine Mode</label>
                    <div className="flex items-center gap-2 bg-surface-container-high rounded-xl px-3 py-2">
                      <code className="text-xs text-on-surface flex-1 font-mono truncate">
                        calle-ai v0.6.0 (Live SDK)
                      </code>
                    </div>
                    <p className="text-[11px] text-on-surface-variant mt-1">Goal-driven phone task engine with JSON Schema validation.</p>
                  </div>

                  <div>
                    <label className="overline mb-1.5 block">CALL-E Terminal Webhook URL</label>
                    <div className="flex items-center gap-2 bg-surface-container-high rounded-xl px-3 py-2">
                      <code className="text-xs text-on-surface flex-1 font-mono truncate">{webhookUrl}</code>
                      <button
                        onClick={() => handleCopy(webhookUrl, "calle_webhook")}
                        className="text-on-surface-variant hover:text-primary transition-colors flex-shrink-0 p-1"
                        title="Copy Webhook URL"
                      >
                        {copiedKey === "calle_webhook" ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                    <p className="text-[11px] text-on-surface-variant mt-1">Configured for instant call result sync to PostgreSQL database.</p>
                  </div>
                </div>
              </div>

              {/* INTEGRATION 5: STRIPE BILLING & SUBSCRIPTION */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start sm:items-center gap-3.5">
                    <div className="w-11 h-11 bg-[#dcfce7] rounded-xl flex items-center justify-center flex-shrink-0 border border-[#bbf7d0]">
                      <CreditCard className="w-6 h-6 text-[#15803d]" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Stripe Subscription & Invoicing</h4>
                        {isStripeConnected ? (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#edf7e0] text-[#396a00] border border-[#d4edba]">
                            <CheckCircle2 className="w-3 h-3" /> {(clinic?.subscription_status === 'active' ? (clinic?.subscription_plan || 'Active') : '14-Day Free Trial').toUpperCase()}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-[#fef3c7] text-[#92400e] border border-[#fde68a]">
                            <AlertCircle className="w-3 h-3" /> Free Tier
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Live payment processing, automated tier billing, invoice downloads, and subscription management.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <button
                      onClick={() => handleTestIntegration('stripe')}
                      disabled={testingService === 'stripe'}
                      className="px-3 py-1.5 rounded-lg border border-surface-container-highest bg-surface-container-high hover:bg-surface-container-highest text-xs font-semibold text-on-surface flex items-center gap-1.5 transition-colors"
                    >
                      {testingService === 'stripe' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5 text-amber-500" />}
                      <span>Verify Billing</span>
                    </button>
                    <button
                      onClick={handleOpenStripePortal}
                      disabled={openingPortal}
                      className="px-4 py-2 rounded-xl text-xs font-bold text-white bg-[#15803d] hover:bg-[#166534] shadow-sm flex items-center gap-2 transition-all active:scale-[0.98]"
                    >
                      {openingPortal ? <Loader2 className="w-4 h-4 animate-spin" /> : <ExternalLink className="w-4 h-4" />}
                      <span>Manage Invoices & Billing</span>
                    </button>
                  </div>
                </div>

                {/* Inline Test Result Banner */}
                {testResult && testResult.service === 'stripe' && (
                  <div className={`p-3 rounded-xl text-xs font-semibold flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-1 ${
                    testResult.success ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]" : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
                  }`}>
                    <div className="flex items-center gap-2">
                      {testResult.success ? <CheckCircle2 className="w-4 h-4 flex-shrink-0" /> : <AlertCircle className="w-4 h-4 flex-shrink-0" />}
                      <span>{testResult.message}</span>
                    </div>
                    <button onClick={() => setTestResult(null)} className="opacity-70 hover:opacity-100 font-bold px-1.5 py-0.5">✕</button>
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-surface-container-high/60">
                  <div>
                    <label className="overline mb-1 block">Stripe Customer ID</label>
                    <div className="px-3 py-2 bg-surface-container-high rounded-xl text-xs font-mono text-on-surface truncate">
                      {clinic?.stripe_customer_id || "Auto-linked on checkout"}
                    </div>
                  </div>
                  <div>
                    <label className="overline mb-1 block">Current Subscription Tier</label>
                    <div className="px-3 py-2 bg-surface-container-high rounded-xl text-xs font-bold text-on-surface uppercase">
                      {clinic?.subscription_plan || clinic?.plan || "Starter"} Plan
                    </div>
                  </div>
                  <div>
                    <label className="overline mb-1 block">Subscription Renewal</label>
                    <div className="px-3 py-2 bg-surface-container-high rounded-xl text-xs font-medium text-on-surface truncate">
                      {clinic?.current_period_end ? new Date(clinic.current_period_end).toLocaleDateString() : (clinic?.trial_ends_at ? new Date(clinic.trial_ends_at).toLocaleDateString() : "Active (Monthly Renewal)")}
                    </div>
                  </div>
                </div>
              </div>

            </div>
          )}

          {/* TAB: AGENT BUILDER */}
          {activeTab === "agent_builder" && (
            <AgentBuilderSettings />
          )}

          {/* TAB: EHR SYNC */}
          {activeTab === "ehr" && isOwner && (
            <EhrSettings />
          )}

          {/* TAB 6: NOTIFICATIONS */}
          {activeTab === "notifications" && (
            <NotificationSettings
              clinicData={clinic}
              onClinicUpdate={(updated) => {
                setClinic(updated);
                if (updated?.notifications_config) {
                  setNotifConfig(updated.notifications_config);
                }
              }}
            />
          )}

          {/* TAB 7: ADVANCED SETUP */}
          {activeTab === "advanced" && (
            <div className="space-y-6">
              <div className="border-b border-surface-container pb-4">
                <h3 className="text-base font-bold text-on-surface flex items-center gap-2">
                  <Sliders className="w-5 h-5 text-primary" /> Advanced Configuration & Developer Engine
                </h3>
                <p className="text-xs text-on-surface-variant mt-1">
                  Manage revenue estimations, recall intervals, industry benchmarking, real-time webhooks, and programmatic REST API keys with 100% database persistence.
                </p>
              </div>

              {/* CARD 1: FINANCIAL & REVENUE PROJECTIONS */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex items-start gap-3.5">
                  <div className="w-10 h-10 bg-[#edf7e0] rounded-xl flex items-center justify-center flex-shrink-0 border border-[#d4edba]">
                    <DollarSign className="w-5 h-5 text-[#396a00]" />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-bold text-on-surface">Monthly Revenue Per Visit ($)</h4>
                    <p className="text-xs text-on-surface-variant mt-0.5">
                      Establishes baseline financial value for AI-booked consultations, missed call recovery projections, and ROI tracking across all dashboards.
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center input-field bg-surface-container-highest gap-2 max-w-md">
                    <DollarSign className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="number"
                      min="0"
                      step="5"
                      value={revenuePerVisit}
                      onChange={(e) => setRevenuePerVisit(parseInt(e.target.value) || 0)}
                      className="flex-1 bg-transparent border-none outline-none text-sm text-on-surface font-semibold"
                      placeholder="150"
                    />
                    <span className="text-xs font-bold text-on-surface-variant/60 uppercase">USD / Visit</span>
                  </div>

                  <div className="flex items-center gap-2 flex-wrap pt-1">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Presets:</span>
                    {[100, 150, 175, 200, 250, 300].map((presetVal) => (
                      <button
                        key={presetVal}
                        type="button"
                        onClick={() => setRevenuePerVisit(presetVal)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                          revenuePerVisit === presetVal
                            ? "bg-primary text-white font-bold"
                            : "bg-surface-container-high hover:bg-surface-container-highest text-on-surface"
                        }`}
                      >
                        ${presetVal}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* CARD 2: PATIENT RECALL CAMPAIGN INTERVALS */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex items-start gap-3.5">
                  <div className="w-10 h-10 bg-blue-50 dark:bg-blue-950/40 rounded-xl flex items-center justify-center flex-shrink-0 border border-blue-200 dark:border-blue-800">
                    <Clock className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-bold text-on-surface">Automated Recall Campaign Cadence (Days)</h4>
                    <p className="text-xs text-on-surface-variant mt-0.5">
                      Specifies days elapsed since a patient's last completed appointment to trigger automated AI outbound reactivation phone calls and SMS campaigns.
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center input-field bg-surface-container-highest gap-2 max-w-md">
                    <Sliders className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                    <input
                      type="text"
                      value={recallDays}
                      onChange={(e) => setRecallDays(e.target.value)}
                      className="flex-1 bg-transparent border-none outline-none text-sm text-on-surface font-mono"
                      placeholder="30, 60, 90"
                    />
                  </div>

                  <div className="flex items-center gap-2 flex-wrap pt-1">
                    <span className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider">Common Cadences:</span>
                    {[
                      { label: "Standard (30, 60, 90)", val: "30, 60, 90" },
                      { label: "Extended (30, 60, 90, 180)", val: "30, 60, 90, 180" },
                      { label: "Frequent (15, 30, 45, 60)", val: "15, 30, 45, 60" },
                      { label: "Semi-Annual (90, 180, 270, 365)", val: "90, 180, 270, 365" }
                    ].map((preset) => (
                      <button
                        key={preset.val}
                        type="button"
                        onClick={() => setRecallDays(preset.val)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all ${
                          recallDays.trim() === preset.val
                            ? "bg-blue-600 text-white font-bold"
                            : "bg-surface-container-high hover:bg-surface-container-highest text-on-surface"
                        }`}
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* CARD 3: ANONYMIZED BENCHMARK OPT-IN */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className="w-10 h-10 bg-emerald-50 dark:bg-emerald-950/40 rounded-xl flex items-center justify-center flex-shrink-0 border border-emerald-200 dark:border-emerald-800">
                      <Sparkles className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Anonymous Specialty Benchmarking</h4>
                        {benchmarkOptIn ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#edf7e0] text-[#396a00] border border-[#d4edba]">
                            Opted-In
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-surface-container-high text-on-surface-variant">
                            Disabled
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                        Share anonymous, aggregated operational metrics (booking conversion rates, after-hours call volumes, no-show trends) to compare your practice against anonymized regional peers in your specialty.
                      </p>
                      <div className="flex items-center gap-2 mt-2 text-[11px] text-[#396a00] font-semibold">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        <span>100% HIPAA & PHI Compliant: Zero patient identifiers or names are ever included or transmitted.</span>
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={() => setBenchmarkOptIn(!benchmarkOptIn)}
                    className={`relative w-12 h-6 rounded-full transition-colors flex-shrink-0 focus:outline-none ${
                      benchmarkOptIn ? "bg-primary" : "bg-surface-container-high"
                    }`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition-transform duration-200 ease-in-out ${
                        benchmarkOptIn ? "translate-x-6" : "translate-x-0"
                      }`}
                    />
                  </button>
                </div>
              </div>

              {/* CARD 4: OUTBOUND WEBHOOKS ENGINE */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className="w-10 h-10 bg-indigo-50 dark:bg-indigo-950/40 rounded-xl flex items-center justify-center flex-shrink-0 border border-indigo-200 dark:border-indigo-800">
                      <Webhook className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-on-surface">Outbound Webhooks Integration</h4>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Stream live operational events (calls, bookings, cancellations, new patient records) to Zapier, Make, n8n, or your custom EHR backend.
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleTestWebhook}
                    disabled={testingWebhook || !outboundWebhookUrl.trim()}
                    className="px-3.5 py-2 rounded-xl text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 shadow-sm transition-all self-start sm:self-auto"
                  >
                    {testingWebhook ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        <span>Sending Test Ping...</span>
                      </>
                    ) : (
                      <>
                        <Send className="w-3.5 h-3.5" />
                        <span>Send Test Ping</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Inline Webhook Test Result Feedback */}
                {webhookTestResult && (
                  <div
                    className={`p-3.5 rounded-xl text-xs font-semibold flex flex-col gap-1.5 animate-in fade-in slide-in-from-top-1 ${
                      webhookTestResult.success
                        ? "bg-[#edf7e0] text-[#396a00] border border-[#d4edba]"
                        : "bg-[#fce4ec] text-[#b71c1c] border border-[#ffcdd2]"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {webhookTestResult.success ? (
                          <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                        ) : (
                          <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        )}
                        <span className="font-bold">{webhookTestResult.message}</span>
                      </div>
                      <button
                        onClick={() => setWebhookTestResult(null)}
                        className="text-xs opacity-70 hover:opacity-100 font-bold px-1.5"
                      >
                        ✕
                      </button>
                    </div>
                    {webhookTestResult.preview && (
                      <div className="mt-1 p-2 rounded bg-black/10 text-[11px] font-mono break-all">
                        Response Preview: {webhookTestResult.preview}
                      </div>
                    )}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                  {/* Webhook URL input */}
                  <div>
                    <label className="overline mb-1.5 block">Webhook Endpoint URL</label>
                    <div className="flex items-center input-field bg-surface-container-highest gap-2">
                      <Globe className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                      <input
                        type="url"
                        value={outboundWebhookUrl}
                        onChange={(e) => setOutboundWebhookUrl(e.target.value)}
                        className="flex-1 bg-transparent border-none outline-none text-xs text-on-surface font-mono"
                        placeholder="https://hooks.zapier.com/hooks/catch/..."
                      />
                      {outboundWebhookUrl && (
                        <button
                          type="button"
                          onClick={() => handleCopy(outboundWebhookUrl, "webhook_endpoint")}
                          className="text-on-surface-variant hover:text-primary transition-colors p-1"
                          title="Copy Webhook URL"
                        >
                          {copiedKey === "webhook_endpoint" ? (
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                    <p className="text-[10px] text-on-surface-variant mt-1">
                      Must be an active HTTPS URL capable of accepting POST requests.
                    </p>
                  </div>

                  {/* Webhook Secret */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <label className="overline block">Webhook Signing Secret (HMAC-SHA256)</label>
                      <button
                        type="button"
                        onClick={handleGenerateWebhookSecret}
                        className="text-[10px] font-bold text-indigo-600 hover:underline flex items-center gap-1"
                      >
                        <RefreshCw className="w-2.5 h-2.5" /> Generate Secret
                      </button>
                    </div>
                    <div className="flex items-center input-field bg-surface-container-highest gap-2">
                      <Lock className="w-4 h-4 text-on-surface-variant flex-shrink-0" />
                      <input
                        type={showWebhookSecret ? "text" : "password"}
                        value={outboundWebhookSecret}
                        onChange={(e) => setOutboundWebhookSecret(e.target.value)}
                        className="flex-1 bg-transparent border-none outline-none text-xs text-on-surface font-mono"
                        placeholder="whsec_..."
                      />
                      <button
                        type="button"
                        onClick={() => setShowWebhookSecret(!showWebhookSecret)}
                        className="text-on-surface-variant hover:text-primary transition-colors p-1"
                        title={showWebhookSecret ? "Hide Secret" : "Show Secret"}
                      >
                        {showWebhookSecret ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                      </button>
                      {outboundWebhookSecret && (
                        <button
                          type="button"
                          onClick={() => handleCopy(outboundWebhookSecret, "webhook_secret")}
                          className="text-on-surface-variant hover:text-primary transition-colors p-1"
                          title="Copy Signing Secret"
                        >
                          {copiedKey === "webhook_secret" ? (
                            <Check className="w-3.5 h-3.5 text-emerald-600" />
                          ) : (
                            <Copy className="w-3.5 h-3.5" />
                          )}
                        </button>
                      )}
                    </div>
                    <p className="text-[10px] text-on-surface-variant mt-1">
                      Header <code className="font-mono">X-Bytelytic-Signature</code> contains the sha256 HMAC of the payload.
                    </p>
                  </div>
                </div>

                {/* Event Subscriptions Checklist */}
                <div className="pt-2 border-t border-surface-container-high/60 space-y-2">
                  <span className="overline block">Event Subscriptions</span>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                    {[
                      { key: "call.completed", label: "Call Completed", desc: "Transcript & recording ready" },
                      { key: "appointment.booked", label: "Appointment Booked", desc: "New appointment scheduled" },
                      { key: "appointment.cancelled", label: "Appointment Cancelled", desc: "Cancellation event" },
                      { key: "patient.created", label: "Patient Registered", desc: "New patient profile created" },
                      { key: "patient.updated", label: "Patient Updated", desc: "Contact / notes updated" }
                    ].map((ev) => {
                      const isChecked = outboundWebhookEvents.includes(ev.key);
                      return (
                        <label
                          key={ev.key}
                          onClick={() => handleToggleWebhookEvent(ev.key)}
                          className={`p-2.5 rounded-xl border flex items-start gap-2.5 cursor-pointer transition-all ${
                            isChecked
                              ? "bg-indigo-50/50 dark:bg-indigo-950/30 border-indigo-200 dark:border-indigo-800"
                              : "bg-surface-container-high/40 border-transparent hover:bg-surface-container-high"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {}} // Handled by label click
                            className="w-4 h-4 accent-indigo-600 rounded mt-0.5"
                          />
                          <div>
                            <span className="text-xs font-bold text-on-surface block">{ev.label}</span>
                            <span className="text-[10px] font-mono text-indigo-600 dark:text-indigo-400 block">{ev.key}</span>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* CARD 5: API KEY MANAGEMENT */}
              <div className="p-5 rounded-2xl bg-surface-container border border-surface-container space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div className="flex items-start gap-3.5">
                    <div className="w-10 h-10 bg-amber-50 dark:bg-amber-950/40 rounded-xl flex items-center justify-center flex-shrink-0 border border-amber-200 dark:border-amber-800">
                      <Key className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Programmatic API Key Management</h4>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-surface-container-high text-on-surface-variant font-mono">
                          {apiKeys.length} Active
                        </span>
                      </div>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Manage programmatic authentication keys for external EHR pipelines, bespoke applications, and server-to-server integrations.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 self-start sm:self-auto">
                    <button
                      type="button"
                      onClick={fetchApiKeys}
                      disabled={loadingApiKeys}
                      className="p-2 rounded-lg border border-surface-container-highest bg-surface-container-high hover:bg-surface-container-highest text-on-surface transition-colors"
                      title="Refresh API Keys"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${loadingApiKeys ? "animate-spin text-primary" : ""}`} />
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setNewKeyName("");
                        setNewKeyScopes(["read", "write"]);
                        setShowNewKeyModal(true);
                      }}
                      className="btn-primary py-2 px-4 text-xs font-bold flex items-center gap-1.5 shadow-sm"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Generate New API Key</span>
                    </button>
                  </div>
                </div>

                {/* API Keys Table / List */}
                <div className="space-y-2 pt-1">
                  {loadingApiKeys && apiKeys.length === 0 ? (
                    <div className="py-8 flex items-center justify-center gap-2 text-xs text-on-surface-variant">
                      <Loader2 className="w-4 h-4 animate-spin text-primary" /> Loading clinic API keys...
                    </div>
                  ) : apiKeys.length === 0 ? (
                    <div className="text-center py-8 border border-dashed border-on-surface-variant/20 rounded-xl bg-surface-container-low/40">
                      <Key className="w-7 h-7 mx-auto text-on-surface-variant/30 mb-2" />
                      <p className="text-xs font-bold text-on-surface">No API keys created yet</p>
                      <p className="text-[11px] text-on-surface-variant/70 mt-0.5">
                        Click 'Generate New API Key' to create a token for programmatic access.
                      </p>
                    </div>
                  ) : (
                    <div className="divide-y divide-surface-container-high rounded-xl border border-surface-container-high overflow-hidden bg-surface">
                      {apiKeys.map((keyItem) => (
                        <div
                          key={keyItem.id}
                          className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-surface-container/30 transition-colors"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-xs font-bold text-on-surface">{keyItem.name || "Default API Key"}</span>
                              <code className="text-[11px] font-mono px-2 py-0.5 rounded bg-surface-container-highest text-on-surface">
                                {keyItem.masked_key || `${keyItem.key_prefix || "by_live_"}...`}
                              </code>
                              {keyItem.masked_key && (
                                <button
                                  type="button"
                                  onClick={() => handleCopy(keyItem.masked_key, `mask_${keyItem.id}`)}
                                  className="text-on-surface-variant/50 hover:text-primary transition-colors"
                                  title="Copy masked token"
                                >
                                  {copiedKey === `mask_${keyItem.id}` ? (
                                    <Check className="w-3 h-3 text-emerald-600" />
                                  ) : (
                                    <Copy className="w-3 h-3" />
                                  )}
                                </button>
                              )}
                            </div>

                            <div className="flex items-center gap-3 text-[11px] text-on-surface-variant flex-wrap">
                              <div className="flex items-center gap-1">
                                <span className="font-semibold">Scopes:</span>
                                {(keyItem.scopes || ["read", "write"]).map((sc) => (
                                  <span
                                    key={sc}
                                    className="px-1.5 py-0.2 rounded text-[10px] font-mono uppercase font-bold bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200 dark:border-amber-800"
                                  >
                                    {sc}
                                  </span>
                                ))}
                              </div>
                              <span>•</span>
                              <span>Created: {keyItem.created_at ? new Date(keyItem.created_at).toLocaleDateString() : "Active"}</span>
                              {keyItem.created_by && (
                                <>
                                  <span>•</span>
                                  <span>By: {keyItem.created_by}</span>
                                </>
                              )}
                            </div>
                          </div>

                          <button
                            type="button"
                            onClick={() => handleRevokeApiKey(keyItem.id, keyItem.name || keyItem.key_prefix)}
                            disabled={revokingKeyId === keyItem.id}
                            className="px-3 py-1.5 text-xs font-bold text-[#b71c1c] hover:bg-[#ffcdd2]/40 rounded-lg transition-colors border border-[#ffcdd2] flex items-center gap-1.5 self-start sm:self-auto disabled:opacity-50"
                            title="Revoke API key"
                          >
                            {revokingKeyId === keyItem.id ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="w-3.5 h-3.5" />
                            )}
                            <span>Revoke Key</span>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: SECURITY & AUDITING */}
          {activeTab === "security" && (
            <SecuritySettings />
          )}

          {/* TAB 8: DANGER ZONE */}
          {activeTab === "danger" && (
            <div className="space-y-6">
              <div className="border-b border-[#ffcdd2] pb-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-bold text-[#d32f2f] flex items-center gap-2">
                      <AlertOctagon className="w-5 h-5" />
                      Danger Zone & HIPAA Compliance Controls
                    </h3>
                    <p className="text-xs text-[#d32f2f]/80 mt-1">
                      High-impact administrative and destructive operations. Proceed with extreme caution.
                    </p>
                  </div>
                  <span className="px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-wider rounded-full bg-[#ffcdd2] text-[#b71c1c]">
                    Owner Only
                  </span>
                </div>
              </div>

              {!isOwner ? (
                <div className="p-5 rounded-xl border border-[#ffcdd2] bg-[#fff5f6] flex items-start gap-3">
                  <ShieldAlert className="w-5 h-5 text-[#d32f2f] flex-shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-sm font-bold text-[#d32f2f]">Owner Privileges Required</h4>
                    <p className="text-xs text-[#d32f2f]/80 mt-1 leading-relaxed">
                      Danger Zone actions (Full PHI Data Export, Account Deactivation, and Factory Reset) are strictly restricted to Clinic Owners. Non-owner staff members are prohibited from exporting patient data or initiating destructive operations.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="space-y-5">
                  {/* CARD 1: Full Clinic Data Export */}
                  <div className="p-5 rounded-xl border border-border bg-card space-y-4 shadow-sm">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-start gap-3">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary flex-shrink-0 mt-0.5">
                          <Archive className="w-5 h-5" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <h4 className="text-sm font-bold text-on-surface">Full Clinic Data Export (JSON & CSV)</h4>
                            <span className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded bg-primary/15 text-primary">
                              HIPAA Data Portability
                            </span>
                          </div>
                          <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                            Download complete clinic operational records including patient profiles, appointments, inbound/outbound call logs & transcripts, SMS communication history, waitlists, and revenue events for HIPAA compliance, external audit, or offline archiving.
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-3 pt-2">
                      <button
                        onClick={() => handleExportClinicData("json")}
                        disabled={exportingFormat !== null}
                        className="py-2 px-4 rounded-lg font-semibold text-xs text-primary bg-primary/10 hover:bg-primary/20 border border-primary/20 flex items-center gap-2 transition-all disabled:opacity-50"
                      >
                        {exportingFormat === "json" ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <FileJson className="w-3.5 h-3.5" />
                        )}
                        {exportingFormat === "json" ? "Exporting JSON..." : "Export as JSON"}
                      </button>

                      <button
                        onClick={() => handleExportClinicData("csv")}
                        disabled={exportingFormat !== null}
                        className="py-2 px-4 rounded-lg font-semibold text-xs text-on-surface bg-surface-container hover:bg-surface-container-high border border-border flex items-center gap-2 transition-all disabled:opacity-50"
                      >
                        {exportingFormat === "csv" ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                        )}
                        {exportingFormat === "csv" ? "Generating CSV Zip..." : "Export as CSV Archive (.zip)"}
                      </button>
                    </div>

                    <div className="bg-surface-container/60 rounded-lg p-2.5 text-[11px] text-on-surface-variant flex items-center gap-2">
                      <ShieldCheck className="w-4 h-4 text-primary flex-shrink-0" />
                      <span>
                        All clinic data exports are permanently recorded in the HIPAA compliance audit trail with caller identity and timestamp.
                      </span>
                    </div>
                  </div>

                  {/* CARD 2: Soft Delete / Account Deactivation */}
                  <div className="p-5 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/20 space-y-4 shadow-sm">
                    <div className="flex items-start gap-3">
                      <div className="w-9 h-9 rounded-lg bg-amber-500/10 flex items-center justify-center text-amber-600 flex-shrink-0 mt-0.5">
                        <UserX className="w-5 h-5" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="text-sm font-bold text-amber-900 dark:text-amber-300">
                            Deactivate / Soft Delete Clinic Account
                          </h4>
                          <span className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-200">
                            Reversible
                          </span>
                        </div>
                        <p className="text-xs text-amber-800/80 dark:text-amber-400/80 mt-1 leading-relaxed">
                          Safely deactivates this clinic workspace. Halts all active AI voice receptionist agents, disables automated SMS reminders/recalls, and restricts dashboard login for staff. Patient data and audit trails are preserved in accordance with medical record retention laws.
                        </p>
                      </div>
                    </div>

                    <div className="pt-2">
                      <button
                        onClick={() => {
                          setSoftDeleteConfirmation("");
                          setSoftDeleteReason("");
                          setShowSoftDeleteModal(true);
                        }}
                        className="py-2.5 px-5 rounded-lg font-bold text-xs text-amber-900 dark:text-amber-200 bg-amber-200 hover:bg-amber-300 dark:bg-amber-900/60 dark:hover:bg-amber-900 border border-amber-300 dark:border-amber-700 transition-all active:scale-[0.98]"
                      >
                        Deactivate Clinic Account
                      </button>
                    </div>
                  </div>

                  {/* CARD 3: Factory Reset / Purge Database */}
                  <div className="p-5 rounded-xl border border-[#ffcdd2] bg-[#fff5f6] space-y-4 shadow-sm">
                    <div className="flex items-start gap-3">
                      <div className="w-9 h-9 rounded-lg bg-[#fce4ec] flex items-center justify-center text-[#d32f2f] flex-shrink-0 mt-0.5">
                        <AlertTriangle className="w-5 h-5" />
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h4 className="text-sm font-bold text-[#d32f2f]">Full Operations Factory Reset</h4>
                          <span className="px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded bg-[#ffcdd2] text-[#b71c1c]">
                            Irreversible
                          </span>
                        </div>
                        <p className="text-xs text-[#d32f2f]/80 mt-1 leading-relaxed">
                          Permanently deletes all operational database records (patients, appointments, call logs, SMS logs, waitlists, and revenue records). Clinic configurations and HIPAA compliance audit logs are strictly preserved.
                        </p>
                      </div>
                    </div>

                    <div className="pt-2">
                      <button
                        onClick={() => {
                          setDeleteConfirmation("");
                          setShowDeleteModal(true);
                        }}
                        className="w-full sm:w-auto py-2.5 px-6 rounded-lg font-bold text-xs text-white bg-[#d32f2f] hover:bg-[#b71c1c] transition-all active:scale-[0.98] shadow-sm"
                      >
                        Factory Reset Clinic Database
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
          </div>
        </div>

        {/* SIDEBAR: SYSTEM HEALTH & QUICK SAVE */}
        <div className="hidden xl:block space-y-5">
          
          {/* Quick save box */}
          {activeTab !== "danger" && (
            <div className="card p-5 flex flex-col items-center justify-center text-center gap-3">
              <div className="w-10 h-10 bg-surface-container rounded-lg flex items-center justify-center flex-shrink-0">
                <Save className="w-5 h-5 text-on-surface-variant" />
              </div>
              <h4 className="text-xs font-bold uppercase tracking-wider text-on-surface">Unsaved Changes</h4>
              <p className="text-[0.6875rem] text-on-surface-variant leading-relaxed">Ensure you save changes before leaving this page.</p>
              
              <button
                onClick={handleSave}
                disabled={saving}
                className="w-full py-2.5 font-bold text-sm rounded-lg transition-all"
                style={{ backgroundColor: "#7dbd42", color: "#fff" }}
              >
                {saving ? "Saving..." : "Save Settings"}
              </button>
            </div>
          )}

          {/* System Status Tracker */}
          <div className="card p-5">
            <div className="flex items-center justify-between gap-2 mb-4">
              <div className="flex items-center gap-2">
                <Shield className="w-4.5 h-4.5 text-primary" />
                <h3 className="text-sm font-bold text-on-surface">System Status</h3>
              </div>
              <button
                onClick={fetchIntegrationsStatus}
                title="Refresh Status"
                className="text-on-surface-variant hover:text-primary transition-colors p-1"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingIntegrations ? "animate-spin text-primary" : ""}`} />
              </button>
            </div>
            
            <div className="space-y-0.5 divide-y divide-surface-container">
              <div className="flex items-center gap-3 py-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#396a00]" />
                <span className="text-xs text-on-surface flex-1">Backend API</span>
                <span className="text-[0.625rem] font-bold text-[#396a00]">Active</span>
              </div>
              
              <div className="flex items-center gap-3 py-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#396a00]" />
                <span className="text-xs text-on-surface flex-1">Database Layer</span>
                <span className="text-[0.625rem] font-bold text-[#396a00]">Active</span>
              </div>
              
              <div className="flex items-center gap-3 py-2">
                <span className={`w-1.5 h-1.5 rounded-full ${isGoogleConnected ? "bg-[#396a00]" : "bg-[#e89e00]"}`} />
                <span className="text-xs text-on-surface flex-1">Google Calendar</span>
                <span className={`text-[0.625rem] font-bold ${isGoogleConnected ? "text-[#396a00]" : "text-[#8a5f00]"}`}>
                  {isGoogleConnected ? "Active" : "Not Linked"}
                </span>
              </div>

              <div className="flex items-center gap-3 py-2">
                <span className={`w-1.5 h-1.5 rounded-full ${isCalleConnected ? "bg-[#396a00]" : "bg-[#e89e00]"}`} />
                <span className="text-xs text-on-surface flex-1">CALL-E Engine</span>
                <span className={`text-[0.625rem] font-bold ${isCalleConnected ? "text-[#396a00]" : "text-[#8a5f00]"}`}>
                  {isCalleConnected ? "Active" : "Ready"}
                </span>
              </div>

              <div className="flex items-center gap-3 py-2">
                <span className={`w-1.5 h-1.5 rounded-full ${isTelnyxConnected ? "bg-[#396a00]" : "bg-[#e89e00]"}`} />
                <span className="text-xs text-on-surface flex-1">Telnyx Line</span>
                <span className={`text-[0.625rem] font-bold ${isTelnyxConnected ? "text-[#396a00]" : "text-[#8a5f00]"}`}>
                  {isTelnyxConnected ? "Active" : "Not Linked"}
                </span>
              </div>

              <div className="flex items-center gap-3 py-2">
                <span className={`w-1.5 h-1.5 rounded-full ${isTwilioConnected ? "bg-[#396a00]" : "bg-[#e89e00]"}`} />
                <span className="text-xs text-on-surface flex-1">Twilio Delivery</span>
                <span className={`text-[0.625rem] font-bold ${isTwilioConnected ? "text-[#396a00]" : "text-[#8a5f00]"}`}>
                  {isTwilioConnected ? "Active" : "Standby"}
                </span>
              </div>

              <div className="flex items-center gap-3 py-2">
                <span className={`w-1.5 h-1.5 rounded-full ${isStripeConnected ? "bg-[#396a00]" : "bg-[#e89e00]"}`} />
                <span className="text-xs text-on-surface flex-1">Stripe Billing</span>
                <span className={`text-[0.625rem] font-bold ${isStripeConnected ? "text-[#396a00]" : "text-[#8a5f00]"}`}>
                  {isStripeConnected ? (clinic?.subscription_status === 'active' ? 'Active' : 'Trial') : "Not Linked"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Compact save bar for non-xl screens */}
      <div className="xl:hidden flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl border border-surface-container bg-surface-container-low mb-6">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <Shield className="w-4 h-4 text-primary flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-xs font-bold text-on-surface">System Status</p>
            <p className="text-[11px] text-on-surface-variant truncate">Backend API · Active &nbsp;·&nbsp; DB Layer · Active</p>
          </div>
        </div>
        {activeTab !== "danger" && (
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn-primary flex items-center gap-2 text-sm py-2.5 px-6 flex-shrink-0"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? "Saving..." : "Save Settings"}
          </button>
        )}
      </div>

      {/* ── Soft Delete / Deactivate Clinic Modal ─────────────── */}
      {showSoftDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="card w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-amber-100 dark:bg-amber-950 flex items-center justify-center text-amber-600 flex-shrink-0">
                <UserX className="w-5 h-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-on-surface">Deactivate Clinic Account</h2>
                <p className="text-xs text-on-surface-variant">Halt receptionist services & staff access</p>
              </div>
            </div>

            <div className="bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 rounded-lg p-3 my-3 text-xs text-amber-900 dark:text-amber-200 space-y-1">
              <p className="font-semibold">Upon deactivation:</p>
              <ul className="list-disc list-inside space-y-0.5 text-[11px] opacity-90">
                <li>AI Voice Receptionist will immediately stop answering calls</li>
                <li>Automated SMS reminders, recalls, and follow-ups will halt</li>
                <li>All staff logins for this clinic workspace will be disabled</li>
                <li>Patient records and audit history remain stored securely</li>
              </ul>
            </div>

            <div className="space-y-3 mt-4">
              <div>
                <label className="overline mb-1 block">
                  To confirm, type <span className="font-mono font-bold text-on-surface">{name || "DELETE ACCOUNT"}</span> or <span className="font-mono font-bold text-on-surface">DELETE ACCOUNT</span>
                </label>
                <input
                  type="text"
                  value={softDeleteConfirmation}
                  onChange={(e) => setSoftDeleteConfirmation(e.target.value)}
                  className="w-full bg-surface-container border border-border focus:border-amber-500 rounded-lg px-3 py-2 text-sm outline-none text-on-surface font-mono"
                  placeholder={name || "DELETE ACCOUNT"}
                />
              </div>

              <div>
                <label className="overline mb-1 block">Reason for Deactivation (Optional)</label>
                <textarea
                  rows={2}
                  value={softDeleteReason}
                  onChange={(e) => setSoftDeleteReason(e.target.value)}
                  className="w-full bg-surface-container border border-border focus:border-primary rounded-lg px-3 py-2 text-xs outline-none text-on-surface resize-none"
                  placeholder="e.g. Temporary closure, moving systems, testing completed..."
                />
              </div>
            </div>

            <div className="flex justify-end gap-3 mt-6 border-t border-surface-container pt-4">
              <button
                onClick={() => {
                  setShowSoftDeleteModal(false);
                  setSoftDeleteConfirmation("");
                  setSoftDeleteReason("");
                }}
                disabled={isSoftDeleting}
                className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSoftDeleteClinic}
                disabled={
                  isSoftDeleting ||
                  (softDeleteConfirmation.trim().toLowerCase() !== (name || "").trim().toLowerCase() &&
                   softDeleteConfirmation.trim() !== "DELETE ACCOUNT")
                }
                className="px-5 py-2 text-xs font-bold text-amber-900 bg-amber-300 hover:bg-amber-400 dark:bg-amber-600 dark:hover:bg-amber-500 dark:text-white rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isSoftDeleting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Deactivating...
                  </>
                ) : (
                  "Deactivate Account"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Factory Reset Modal ───────────────────────────────── */}
      {showDeleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="card w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-full bg-[#fce4ec] flex items-center justify-center text-[#d32f2f] flex-shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h2 className="text-lg font-bold text-on-surface">Factory Reset Clinic Database</h2>
            </div>

            <div className="bg-[#fff5f6] border border-[#ffcdd2] rounded-lg p-3 my-3 text-xs text-[#b71c1c] space-y-1">
              <p className="font-bold">Permanent Deletion Warning:</p>
              <p className="text-[11px] leading-relaxed">
                This operation permanently purges <strong className="underline">all patients, appointments, call transcripts, SMS messages, waitlists, and revenue events</strong>.
              </p>
              <p className="text-[11px] text-on-surface-variant pt-1">
                Clinic profiles, staff accounts, and HIPAA compliance audit logs are strictly preserved.
              </p>
            </div>

            <div className="mb-4">
              <label className="overline mb-1.5 block">
                Please type <span className="text-[#d32f2f] font-mono font-bold">DELETE EVERYTHING</span> to confirm:
              </label>
              <input
                type="text"
                value={deleteConfirmation}
                onChange={(e) => setDeleteConfirmation(e.target.value)}
                className="w-full bg-surface-container border border-error/30 focus:border-error rounded-lg px-3 py-2 text-sm outline-none text-on-surface font-mono"
                placeholder="DELETE EVERYTHING"
              />
            </div>

            <div className="flex justify-end gap-3 mt-6 border-t border-surface-container pt-4">
              <button
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeleteConfirmation("");
                }}
                disabled={isWiping}
                className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleFactoryReset}
                disabled={isWiping || deleteConfirmation.trim() !== "DELETE EVERYTHING"}
                className="px-5 py-2 text-xs font-bold text-white bg-[#d32f2f] hover:bg-[#b71c1c] rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isWiping ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Wiping Operational Records...
                  </>
                ) : (
                  "I understand, delete data"
                )}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* ── Generate API Key Modal ────────────────────────────── */}
      {showNewKeyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="card w-full max-w-md p-6 animate-in zoom-in-95 duration-200 shadow-2xl border border-surface-container-highest">
            <div className="flex items-center justify-between pb-3 border-b border-surface-container">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950/50 flex items-center justify-center text-amber-600 dark:text-amber-400">
                  <Key className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-on-surface">Generate New API Key</h3>
              </div>
              <button
                type="button"
                onClick={() => setShowNewKeyModal(false)}
                className="text-on-surface-variant/60 hover:text-on-surface p-1 rounded-lg"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateApiKey} className="space-y-4 mt-4">
              <div>
                <label className="overline mb-1.5 block">Key Label / Friendly Name</label>
                <input
                  type="text"
                  required
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  placeholder="e.g. Zapier Webhook Sync or EHR Integration"
                  className="input-field w-full text-xs"
                />
                <p className="text-[10px] text-on-surface-variant mt-1">
                  A descriptive identifier to recognize what system uses this key.
                </p>
              </div>

              <div>
                <label className="overline mb-1.5 block">Access Scopes</label>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { id: "read", label: "Read Access", desc: "Query patients & appointments" },
                    { id: "write", label: "Write Access", desc: "Create & update records" }
                  ].map((scopeItem) => {
                    const isSelected = newKeyScopes.includes(scopeItem.id);
                    return (
                      <label
                        key={scopeItem.id}
                        onClick={() => {
                          setNewKeyScopes((prev) =>
                            prev.includes(scopeItem.id)
                              ? prev.filter((s) => s !== scopeItem.id)
                              : [...prev, scopeItem.id]
                          );
                        }}
                        className={`p-2.5 rounded-xl border flex items-start gap-2 cursor-pointer transition-all ${
                          isSelected
                            ? "bg-amber-50/60 dark:bg-amber-950/40 border-amber-300 dark:border-amber-700"
                            : "bg-surface-container-high/40 border-transparent hover:bg-surface-container-high"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="w-3.5 h-3.5 accent-amber-600 rounded mt-0.5"
                        />
                        <div>
                          <span className="text-xs font-bold text-on-surface block">{scopeItem.label}</span>
                          <span className="text-[10px] text-on-surface-variant block">{scopeItem.desc}</span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="flex justify-end gap-2.5 pt-3 border-t border-surface-container">
                <button
                  type="button"
                  onClick={() => setShowNewKeyModal(false)}
                  disabled={creatingKey}
                  className="px-4 py-2 text-xs font-semibold text-on-surface hover:bg-surface-container rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creatingKey || !newKeyName.trim()}
                  className="btn-primary py-2 px-5 text-xs font-bold flex items-center gap-1.5 disabled:opacity-50"
                >
                  {creatingKey ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                  <span>Generate Key</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Newly Created API Key Reveal Modal ─────────────────── */}
      {createdKeyData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="card w-full max-w-lg p-6 animate-in zoom-in-95 duration-200 shadow-2xl border border-emerald-300 dark:border-emerald-800 space-y-4">
            <div className="flex items-center gap-3 pb-3 border-b border-surface-container">
              <div className="w-10 h-10 rounded-xl bg-[#edf7e0] flex items-center justify-center text-[#396a00] flex-shrink-0 border border-[#d4edba]">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-on-surface">API Key Created Successfully</h3>
                <p className="text-xs text-on-surface-variant">
                  Key: <strong className="text-on-surface">{createdKeyData.name}</strong>
                </p>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-[#fffbeb] dark:bg-amber-950/40 border border-[#fef3c7] dark:border-amber-800 text-xs text-[#92400e] dark:text-amber-200 flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
              <div className="leading-relaxed">
                <strong>Important Security Notice:</strong> Please copy this API key now. For your security, this secret token will <strong>never be shown again</strong>. If you lose it, you will need to revoke this key and generate a new one.
              </div>
            </div>

            <div>
              <label className="overline mb-1 block">Your Live API Secret Key</label>
              <div className="flex items-center input-field bg-surface-container-highest gap-2 p-2 rounded-xl">
                <Key className="w-4 h-4 text-amber-600 flex-shrink-0" />
                <input
                  type="text"
                  readOnly
                  value={createdKeyData.apiKey || ""}
                  className="flex-1 bg-transparent border-none outline-none text-xs text-on-surface font-mono font-bold select-all"
                />
                <button
                  type="button"
                  onClick={() => handleCopy(createdKeyData.apiKey, "new_raw_api_key")}
                  className="btn-primary py-1.5 px-3 text-xs flex items-center gap-1.5 shadow-none"
                >
                  {copiedKey === "new_raw_api_key" ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-white" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy Key</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between text-[11px] text-on-surface-variant pt-2 border-t border-surface-container">
              <span>Scopes: {createdKeyData.scopes?.join(", ") || "read, write"}</span>
              <button
                type="button"
                onClick={() => setCreatedKeyData(null)}
                className="px-5 py-2 text-xs font-bold text-white bg-primary hover:bg-primary/90 rounded-lg transition-all"
              >
                I have securely copied my API Key
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
