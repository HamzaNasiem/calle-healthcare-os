import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  X,
  Calendar,
  Clock,
  User,
  Phone,
  Mail,
  Shield,
  Bot,
  AlertCircle,
  CheckCircle,
  Search,
  Sparkles,
  Loader,
  Sliders,
  Check,
  Stethoscope,
  Lock,
} from "lucide-react";
import api from "../lib/api";

const DEFAULT_TZ = "America/Chicago";

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

const parseInTimezone = (dateStr, timeStr, tz = DEFAULT_TZ) => {
  if (!dateStr || !timeStr) return null;
  const naiveIso = `${dateStr}T${timeStr}:00Z`;
  const tempDate = new Date(naiveIso);
  if (isNaN(tempDate.getTime())) return null;

  try {
    const formatter = new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "numeric",
      second: "numeric",
      hour12: false,
    });
    const parts = formatter.formatToParts(tempDate);
    const y = parseInt(parts.find((p) => p.type === "year").value, 10);
    const m = parseInt(parts.find((p) => p.type === "month").value, 10);
    const d = parseInt(parts.find((p) => p.type === "day").value, 10);
    let h = parseInt(parts.find((p) => p.type === "hour").value, 10);
    if (h === 24) h = 0;
    const min = parseInt(parts.find((p) => p.type === "minute").value, 10);
    const s = parseInt(parts.find((p) => p.type === "second").value, 10);

    const formattedTzDate = Date.UTC(y, m - 1, d, h, min, s);
    const offsetMs = formattedTzDate - tempDate.getTime();
    return new Date(tempDate.getTime() - offsetMs);
  } catch (e) {
    return new Date(`${dateStr}T${timeStr}`);
  }
};

const AppointmentModal = ({
  isOpen = true,
  onClose,
  onCreated,
  timezone = DEFAULT_TZ,
  initialDate = "",
  existingAppointments = [],
  appointmentTypes = [],
  doctors = [],
}) => {
  const [isBlock, setIsBlock] = useState(false);
  const [availableTypes, setAvailableTypes] = useState(
    Array.isArray(appointmentTypes) && appointmentTypes.length > 0
      ? appointmentTypes
      : [
          { name: "Initial Evaluation", duration: 60, duration_minutes: 60, fee: 150 },
          { name: "Follow-up Consultation", duration: 30, duration_minutes: 30, fee: 75 },
          { name: "Routine Checkup", duration: 30, duration_minutes: 30, fee: 80 },
          { name: "Telehealth Review", duration: 15, duration_minutes: 15, fee: 50 },
        ]
  );

  const [providerList, setProviderList] = useState(
    Array.isArray(doctors) && doctors.length > 0
      ? doctors
      : [
          { id: "doc-1", name: "Dr. Sarah Jenkins", specialty: "General Practice" },
          { id: "doc-2", name: "Dr. Alex Taylor", specialty: "Internal Medicine" },
          { id: "doc-3", name: "Dr. Michael Chang", specialty: "Cardiology" },
        ]
  );

  const [form, setForm] = useState({
    patient_id: "",
    patient_name: "",
    patient_phone: "",
    patient_email: "",
    doctor_name: (doctors && doctors[0]?.name) || "Dr. Sarah Jenkins",
    doctor_id: (doctors && doctors[0]?.id) || "doc-1",
    appointment_type: (appointmentTypes && appointmentTypes[0]?.name) || "Initial Evaluation",
    date: initialDate || new Date().toISOString().split("T")[0],
    time: "09:00",
    duration_minutes: (appointmentTypes && (appointmentTypes[0]?.duration_minutes || appointmentTypes[0]?.duration)) || 60,
    block_type: "Lunch Break",
    custom_block_title: "",
    notes: "",
    send_sms: true,
    queue_calle: true,
  });

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [dateAppointments, setDateAppointments] = useState([]);
  const [overrideConflict, setOverrideConflict] = useState(false);

  // Live Patient Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSearchResults, setShowSearchResults] = useState(false);
  const searchTimeoutRef = useRef(null);

  // Sync types and doctors
  useEffect(() => {
    if (Array.isArray(appointmentTypes) && appointmentTypes.length > 0) {
      setAvailableTypes(appointmentTypes);
      const matched = appointmentTypes.find((t) => t.name === form.appointment_type) || appointmentTypes[0];
      setForm((f) => ({
        ...f,
        appointment_type: matched?.name || f.appointment_type,
        duration_minutes: matched?.duration_minutes || matched?.duration || f.duration_minutes,
      }));
    }
  }, [appointmentTypes]);

  useEffect(() => {
    if (Array.isArray(doctors) && doctors.length > 0) {
      setProviderList(doctors);
      if (!form.doctor_name) {
        setForm((f) => ({
          ...f,
          doctor_name: doctors[0].name || doctors[0].display_name,
          doctor_id: doctors[0].id || doctors[0].user_id,
        }));
      }
    }
  }, [doctors]);

  // Load appointments on the selected date for real-time conflict checking
  useEffect(() => {
    if (!form.date) return;
    let active = true;
    const loadDateAppts = async () => {
      try {
        const startUtc = parseInTimezone(form.date, "00:00", timezone);
        const endUtc = parseInTimezone(form.date, "23:59", timezone);
        if (!startUtc || !endUtc) return;
        const res = await api.get(
          `/appointments?date_from=${startUtc.toISOString()}&date_to=${endUtc.toISOString()}&limit=100`
        );
        if (active && res.data?.data) {
          setDateAppointments(res.data.data);
        }
      } catch (err) {
        console.error("Failed to load appointments for conflict check:", err);
      }
    };
    loadDateAppts();
    return () => {
      active = false;
    };
  }, [form.date, timezone]);

  // Patient Search Handler
  const handleSearchChange = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    setForm((f) => ({ ...f, patient_name: val }));

    if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);

    if (val.trim().length < 2) {
      setSearchResults([]);
      setShowSearchResults(false);
      return;
    }

    setIsSearching(true);
    searchTimeoutRef.current = setTimeout(async () => {
      try {
        const res = await api.get(`/patients?search=${encodeURIComponent(val)}&limit=6`);
        setSearchResults(res.data?.data || []);
        setShowSearchResults(true);
      } catch (err) {
        console.error("Patient search error:", err);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 300);
  };

  const handleSelectPatient = (patient) => {
    setForm((f) => ({
      ...f,
      patient_id: patient.id,
      patient_name: patient.name || patient.full_name || "",
      patient_phone: patient.phone || "",
      patient_email: patient.email || "",
    }));
    setSearchQuery(patient.name || patient.full_name || "");
    setShowSearchResults(false);
  };

  // Conflict calculation
  const currentStart = parseInTimezone(form.date, form.time, timezone)?.getTime();
  const currentEnd = currentStart ? currentStart + Number(form.duration_minutes) * 60 * 1000 : null;

  const conflicts = [];
  const isPast = currentStart ? currentStart < Date.now() - 5 * 60 * 1000 : false;

  if (currentStart && currentEnd && !isPast) {
    const listToCheck = dateAppointments.length > 0 ? dateAppointments : existingAppointments || [];
    for (const apt of listToCheck) {
      if (apt.status === "cancelled") continue;
      const aptStart = new Date(apt.datetime).getTime();
      const aptEnd = aptStart + Number(apt.duration_minutes || 30) * 60 * 1000;

      if (currentStart < aptEnd && aptStart < currentEnd) {
        conflicts.push(apt);
      }
    }
  }

  // Format phone helper
  const formatPhoneInput = (val) => {
    const digits = val.replace(/\D/g, "");
    if (digits.length <= 10) {
      if (digits.length < 4) return digits;
      if (digits.length < 7) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
      return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
    }
    return val;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    const finalName = isBlock
      ? `[BLOCKED] ${form.block_type === "Other" ? form.custom_block_title || "Busy Block" : form.block_type}`
      : form.patient_name;

    const finalPhone = isBlock ? "+10000000000" : form.patient_phone;
    const finalApptType = isBlock ? "Blocked Time" : form.appointment_type;

    if (!finalName.trim()) {
      setError("Please specify patient name or block reason.");
      return;
    }
    if (!isBlock && !finalPhone.trim()) {
      setError("Patient contact phone number is required.");
      return;
    }
    if (!form.date || !form.time) {
      setError("Please choose a valid appointment date and time.");
      return;
    }

    const selectedUtc = parseInTimezone(form.date, form.time, timezone);
    if (selectedUtc && selectedUtc < new Date(Date.now() - 5 * 60 * 1000)) {
      setError("Cannot book an appointment or block availability in the past.");
      return;
    }

    if (conflicts.length > 0 && !overrideConflict) {
      setError("Please confirm 'I understand there is a conflict' to force-book this time slot.");
      return;
    }

    setSaving(true);
    try {
      const datetime = `${form.date}T${form.time}:00`;

      let formattedPhone = finalPhone.trim();
      if (!isBlock && formattedPhone) {
        const rawDigits = formattedPhone.replace(/\D/g, "");
        if (formattedPhone.startsWith("+")) {
          formattedPhone = "+" + rawDigits;
        } else if (rawDigits.length === 10) {
          formattedPhone = "+1" + rawDigits; // Standard 10-digit US number
        } else if (rawDigits.length === 11 && rawDigits.startsWith("1")) {
          formattedPhone = "+" + rawDigits;
        } else if (rawDigits.startsWith("03") && rawDigits.length === 11) {
          formattedPhone = "+92" + rawDigits.slice(1);
        } else {
          formattedPhone = "+" + rawDigits;
        }
      }


      await api.post("/appointments", {
        patient_id: form.patient_id || undefined,
        patient_name: finalName,
        patient_phone: formattedPhone,
        appointment_type: finalApptType,
        datetime,
        duration_minutes: Number(form.duration_minutes),
        notes: form.notes || undefined,
        doctor_name: form.doctor_name || undefined,
        send_confirmation_sms: form.send_sms,
      });

      if (onCreated) onCreated();
      if (onClose) onClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        setError(detail[0]?.msg || "Validation error in form.");
      } else {
        setError(err.response?.data?.error || detail || "Failed to schedule appointment.");
      }
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-white border border-[#edf1ef] w-full max-w-xl p-6 rounded-3xl shadow-2xl relative my-auto animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-[#edf1ef]">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[0.65rem] font-black tracking-widest text-[#396a00] uppercase bg-[#7FCD4D]/15 px-2 py-0.5 rounded-md">
                CALENDAR SCHEDULER
              </span>
              <span className="text-[0.65rem] text-slate-400 font-semibold flex items-center gap-1">
                <Lock className="w-3 h-3 text-slate-400" /> Slot Locking Active
              </span>
            </div>
            <h2 className="text-lg font-black text-[#181c1c]">
              {isBlock ? "Block Clinic Availability" : "Schedule New Appointment"}
            </h2>
            <p className="text-xs text-on-surface-variant mt-0.5 font-medium">
              {isBlock
                ? "Close out calendar time slots for doctor rounds, lunch, or staff meetings."
                : "Book a patient appointment with automated instant SMS and CALL-E voice confirmation."}
            </p>
          </div>
          <button
            onClick={onClose}
            type="button"
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-all border-none bg-transparent cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Switcher: Patient Booking vs Block */}
        <div className="flex bg-slate-100 p-1 rounded-2xl gap-1 my-4 border border-slate-200/50">
          <button
            type="button"
            onClick={() => setIsBlock(false)}
            className={`flex-1 py-2 text-xs font-black rounded-xl transition-all border-none cursor-pointer flex items-center justify-center gap-1.5 ${
              !isBlock
                ? "bg-white shadow-sm text-[#396a00]"
                : "text-slate-500 hover:text-slate-900 bg-transparent"
            }`}
          >
            <User className="w-3.5 h-3.5" />
            Patient Booking
          </button>
          <button
            type="button"
            onClick={() => setIsBlock(true)}
            className={`flex-1 py-2 text-xs font-black rounded-xl transition-all border-none cursor-pointer flex items-center justify-center gap-1.5 ${
              isBlock
                ? "bg-white shadow-sm text-[#396a00]"
                : "text-slate-500 hover:text-slate-900 bg-transparent"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            Busy Block / Vacation
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {!isBlock ? (
            <>
              {/* Patient Live Search and Autofill */}
              <div className="relative">
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                  Patient Search & Name *
                </label>
                <div className="relative">
                  <input
                    type="text"
                    className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl pl-9 pr-3 py-2.5 text-xs outline-none text-[#181c1c] font-semibold transition-all"
                    placeholder="Search by patient name or phone, or type new patient..."
                    value={searchQuery}
                    onChange={handleSearchChange}
                    onFocus={() => searchResults.length > 0 && setShowSearchResults(true)}
                  />
                  <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  {isSearching && (
                    <Loader className="w-3.5 h-3.5 text-[#396a00] animate-spin absolute right-3 top-3" />
                  )}
                </div>

                {/* Dropdown search results */}
                {showSearchResults && searchResults.length > 0 && (
                  <div className="absolute z-20 top-full left-0 right-0 mt-1 bg-white border border-slate-200 rounded-2xl shadow-xl max-h-48 overflow-y-auto thin-scrollbar p-1.5 space-y-1">
                    <p className="text-[9px] font-black text-slate-400 px-2 py-1 uppercase tracking-wider">
                      Existing Patient Matches
                    </p>
                    {searchResults.map((pat) => (
                      <div
                        key={pat.id}
                        onClick={() => handleSelectPatient(pat)}
                        className="px-3 py-2 hover:bg-emerald-50 rounded-xl cursor-pointer transition-all flex items-center justify-between text-xs"
                      >
                        <div>
                          <p className="font-bold text-[#181c1c]">{pat.name || pat.full_name}</p>
                          <p className="text-[10px] text-slate-500 font-medium">
                            {pat.phone} {pat.email ? `• ${pat.email}` : ""}
                          </p>
                        </div>
                        <span className="text-[9px] font-bold px-2 py-0.5 bg-slate-100 text-slate-700 rounded-md">
                          {pat.total_visits || 0} visits
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Phone & Email Row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                    Phone Number (SMS & Calls) *
                  </label>
                  <div className="relative">
                    <input
                      type="tel"
                      className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl pl-9 pr-3 py-2.5 text-xs outline-none text-[#181c1c] font-semibold transition-all font-mono"
                      placeholder="(555) 000-0000"
                      value={form.patient_phone}
                      onChange={(e) =>
                        setForm((f) => ({ ...f, patient_phone: formatPhoneInput(e.target.value) }))
                      }
                    />
                    <Phone className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  </div>
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                    Email Address (Optional)
                  </label>
                  <div className="relative">
                    <input
                      type="email"
                      className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl pl-9 pr-3 py-2.5 text-xs outline-none text-[#181c1c] font-semibold transition-all"
                      placeholder="patient@example.com"
                      value={form.patient_email}
                      onChange={(e) => setForm((f) => ({ ...f, patient_email: e.target.value }))}
                    />
                    <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                  </div>
                </div>
              </div>

              {/* Provider & Service Row */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                    Assigned Doctor / Provider *
                  </label>
                  <div className="relative">
                    <select
                      className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl pl-9 pr-3 py-2.5 text-xs outline-none text-[#181c1c] font-bold transition-all cursor-pointer appearance-none"
                      value={form.doctor_name}
                      onChange={(e) => {
                        const val = e.target.value;
                        const match = providerList.find((p) => (p.name || p.display_name) === val);
                        setForm((f) => ({
                          ...f,
                          doctor_name: val,
                          doctor_id: match?.id || match?.user_id || f.doctor_id,
                        }));
                      }}
                    >
                      {providerList.map((p, idx) => (
                        <option key={idx} value={p.name || p.display_name}>
                          {p.name || p.display_name} ({p.specialty || "Clinician"})
                        </option>
                      ))}
                    </select>
                    <Stethoscope className="w-4 h-4 text-[#396a00] absolute left-3 top-3" />
                  </div>
                </div>

                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                    Service Type & Duration
                  </label>
                  <select
                    className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl px-3 py-2.5 text-xs outline-none text-[#181c1c] font-bold transition-all cursor-pointer"
                    value={form.appointment_type}
                    onChange={(e) => {
                      const val = e.target.value;
                      const matched = availableTypes.find((t) => t.name === val);
                      setForm((f) => ({
                        ...f,
                        appointment_type: val,
                        duration_minutes:
                          matched?.duration_minutes || matched?.duration || f.duration_minutes || 30,
                      }));
                    }}
                  >
                    {availableTypes.map((t, idx) => (
                      <option key={idx} value={t.name}>
                        {t.name} ({t.duration_minutes || t.duration || 30}m{t.fee ? ` • $${t.fee}` : ""})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </>
          ) : (
            <>
              {/* Busy Block details */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                  Block Category *
                </label>
                <select
                  className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl px-3 py-2.5 text-xs outline-none text-[#181c1c] font-bold transition-all cursor-pointer"
                  value={form.block_type}
                  onChange={(e) => setForm((f) => ({ ...f, block_type: e.target.value }))}
                >
                  <option value="Lunch Break">Lunch Break</option>
                  <option value="Staff Meeting">Staff Meeting / Briefing</option>
                  <option value="Vacation / Out of Office">Vacation / Out of Office</option>
                  <option value="Doctor Rounds">Doctor Hospital Rounds</option>
                  <option value="Personal Break">Personal Break</option>
                  <option value="Other">Other Custom Block</option>
                </select>
              </div>

              {form.block_type === "Other" && (
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                    Custom Block Description *
                  </label>
                  <input
                    type="text"
                    className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl px-3 py-2 text-xs outline-none text-[#181c1c] font-semibold transition-all"
                    placeholder="E.g., Medical Equipment Maintenance"
                    value={form.custom_block_title}
                    onChange={(e) => setForm((f) => ({ ...f, custom_block_title: e.target.value }))}
                  />
                </div>
              )}
            </>
          )}

          {/* Date, Time, Duration Grid */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                Date *
              </label>
              <input
                type="date"
                className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl px-3 py-2 text-xs outline-none text-[#181c1c] font-bold transition-all font-mono"
                value={form.date}
                onChange={(e) => setForm((f) => ({ ...f, date: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                Time *
              </label>
              <input
                type="time"
                className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl px-3 py-2 text-xs outline-none text-[#181c1c] font-bold transition-all font-mono"
                value={form.time}
                onChange={(e) => setForm((f) => ({ ...f, time: e.target.value }))}
              />
            </div>
            <div>
              <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
                Duration
              </label>
              <select
                className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl px-3 py-2 text-xs outline-none text-[#181c1c] font-bold transition-all cursor-pointer"
                value={form.duration_minutes}
                onChange={(e) => setForm((f) => ({ ...f, duration_minutes: e.target.value }))}
              >
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={45}>45 min</option>
                <option value={60}>60 min</option>
                <option value={90}>90 min</option>
                <option value={120}>120 min (2h)</option>
              </select>
            </div>
          </div>

          {/* Conflict warnings */}
          {isPast && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-2xl text-red-800 text-xs flex gap-2.5 items-start">
              <AlertCircle className="w-4 h-4 text-red-600 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-bold text-red-900">Past Date/Time Selected</p>
                <p className="text-[11px] opacity-90 mt-0.5 leading-relaxed">
                  Appointments cannot be booked in the past. Please choose a future slot.
                </p>
              </div>
            </div>
          )}

          {!isPast && conflicts.length > 0 && (
            <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-2xl space-y-2.5">
              <div className="flex gap-2 items-start text-amber-900 text-xs">
                <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5 animate-pulse" />
                <div>
                  <p className="font-bold text-amber-950">Active Slot Conflict Detected</p>
                  <p className="text-[11px] opacity-90 mt-0.5 leading-relaxed">
                    This time overlaps with {conflicts.length} scheduled event(s):
                  </p>
                </div>
              </div>
              <div className="space-y-1 pl-6 max-h-20 overflow-y-auto thin-scrollbar">
                {conflicts.map((apt) => (
                  <div key={apt.id} className="text-[11px] font-bold text-amber-950">
                    • {apt.patient_name} ({fmtClinicTime(apt.datetime, timezone)})
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-2 pt-2 border-t border-amber-200/60">
                <input
                  type="checkbox"
                  id="overrideModalConflict"
                  checked={overrideConflict}
                  onChange={(e) => setOverrideConflict(e.target.checked)}
                  className="h-4 w-4 text-[#396a00] border-amber-300 rounded focus:ring-[#396a00] cursor-pointer"
                />
                <label
                  htmlFor="overrideModalConflict"
                  className="text-xs font-bold text-amber-950 cursor-pointer select-none"
                >
                  I understand there is a conflict and want to double-book anyway.
                </label>
              </div>
            </div>
          )}

          {/* Automated communication triggers */}
          {!isBlock && (
            <div className="p-3 bg-emerald-50/70 border border-emerald-200/60 rounded-2xl space-y-2 text-xs">
              <div className="flex items-center gap-2 text-[#396a00] font-bold">
                <Sparkles className="w-3.5 h-3.5" />
                <span>Automated Patient Workflows</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] text-[#181c1c] font-medium pt-1">
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={form.send_sms}
                    onChange={(e) => setForm((f) => ({ ...f, send_sms: e.target.checked }))}
                    className="h-3.5 w-3.5 text-[#396a00] rounded focus:ring-[#396a00]"
                  />
                  <span>Instant Telnyx SMS confirmation</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <input
                    type="checkbox"
                    checked={form.queue_calle}
                    onChange={(e) => setForm((f) => ({ ...f, queue_calle: e.target.checked }))}
                    className="h-3.5 w-3.5 text-[#396a00] rounded focus:ring-[#396a00]"
                  />
                  <span>CALL-E 24h voice confirmation</span>
                </label>
              </div>
            </div>
          )}

          {/* Notes field */}
          <div>
            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 block">
              Clinical Instructions & Notes
            </label>
            <textarea
              className="w-full bg-slate-50 border border-slate-200 focus:border-[#396a00] focus:ring-2 focus:ring-[#7FCD4D]/20 rounded-xl p-2.5 text-xs outline-none text-[#181c1c] font-medium resize-none h-16 transition-all"
              placeholder="Add prep instructions, medical symptoms, or patient requests..."
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>

          {error && (
            <p className="text-xs font-bold text-red-600 bg-red-50 p-2.5 rounded-xl border border-red-200">
              {error}
            </p>
          )}

          {/* Footer Actions */}
          <div className="flex justify-end gap-2.5 pt-3 border-t border-[#edf1ef]">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all border-none cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving || isPast || (conflicts.length > 0 && !overrideConflict)}
              className="btn-primary text-xs px-5 py-2.5 font-bold flex items-center gap-1.5 disabled:opacity-50 border-none cursor-pointer shadow-md shadow-[#396a00]/20"
            >
              {saving ? (
                <>
                  <Loader className="w-3.5 h-3.5 animate-spin" />
                  Booking Slot...
                </>
              ) : conflicts.length > 0 ? (
                "Force Book Slot"
              ) : isBlock ? (
                "Block Availability"
              ) : (
                "Confirm & Schedule"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default AppointmentModal;
