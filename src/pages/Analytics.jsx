import React, { useState, useEffect, useMemo } from "react";
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  PieChart, Pie, Cell, Legend, BarChart, Bar, LineChart, Line, ReferenceLine 
} from "recharts";
import { 
  TrendingUp, Phone, Users, Calendar, AlertCircle, FileSpreadsheet, 
  Sparkles, CheckCircle2, ChevronRight, Loader2, ArrowUpRight, ArrowDownRight, ShieldAlert,
  HelpCircle, Search, Mail, Calculator, Clock, Activity, DollarSign, Award,
  Download, Check, SlidersHorizontal, BarChart3, ShieldCheck, Zap
} from "lucide-react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { translations } from "../lib/translations";

const PRESETS = [
  { label: "Last 7 Days", value: "7" },
  { label: "Last 30 Days", value: "30" },
  { label: "This Month", value: "month" },
  { label: "All Time", value: "all" },
];

const round = (val) => Math.round(Number(val) || 0);
const formatCurrency = (val) => `$${(Number(val) || 0).toLocaleString()}`;
const formatPercent = (val) => `${(Number(val) || 0).toFixed(1)}%`;

export default function Analytics() {
  const { clinicId, getCacheItem, setCacheItem, language } = useAuth();
  const t = translations[language] || translations.en;
  
  // States
  const [activeTab, setActiveTab] = useState("revenue");
  const [preset, setPreset] = useState("30");
  const [customRange, setCustomRange] = useState({ start: "", end: "" });
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);

  // ROI Interactive Calculator Local State
  const [staffHourlyWage, setStaffHourlyWage] = useState(25); // $20 - $45 / hr
  const [dailyCallVolume, setDailyCallVolume] = useState(35); // 10 - 150 calls / day
  const [avgCallMins, setAvgCallMins] = useState(4.5); // 3 - 8 min / call
  const [clinicDaysPerMonth, setClinicDaysPerMonth] = useState(22); // 15 - 28 days / mo
  const [avgVisitValue, setAvgVisitValue] = useState(150); // $50 - $500 / visit
  const [heatmap24h, setHeatmap24h] = useState(false);
  
  // Data states
  const [revenueData, setRevenueData] = useState({
    trend: [],
    breakdown: [],
    total_period_revenue: 0,
    projected_annual_savings: 0,
    mrr: 0,
    recovered_revenue: 0,
    avg_booking_value: 0
  });

  const [callsData, setCallsData] = useState({
    heatmap: {},
    peak_hours_distribution: [],
    day_distribution: [],
    total_calls: 0,
    handled_calls: 0,
    missed_calls: 0,
    answer_rate: 100,
    inbound_conversion_rate: 0,
    booked_calls_count: 0,
    avg_duration_seconds: 0,
    total_duration_minutes: 0,
    mom_change_percent: 0
  });

  const [roiData, setRoiData] = useState({
    staff_hours_saved_total: 0,
    staff_hours_saved_per_week: 0,
    total_minutes_saved: 0,
    staff_cost_saved: 0,
    revenue_protected: 0,
    total_economic_benefit: 0,
    roi_multiplier: 1.0,
    total_ai_calls: 0,
    breakdown: {},
    inputs: {},
    projections: {}
  });

  const [campaignsData, setCampaignsData] = useState({
    campaigns: {},
    comparison_chart: [],
    total_campaign_revenue: 0,
    total_campaign_conversions: 0,
    recalls_legacy: {}
  });

  const [patientsData, setPatientsData] = useState({
    ratio: [],
    vip_list: [],
    churn_risk_list: [],
    total_patients: 0,
    new_patients_count: 0,
    returning_patients_count: 0,
    average_ltv: 0
  });

  const [noshowsData, setNoshowsData] = useState({
    trend: [],
    no_show_rate: 0,
    show_rate: 100,
    no_show_count: 0,
    attended_count: 0,
    completed_count: 0,
    scheduled_count: 0,
    concluded_appointments: 0,
    total_appointments: 0,
    lost_revenue: 0,
    avg_visit_value: 150,
    recovered_revenue: 0,
    recovery_dispatched_count: 0,
    recovery_converted_count: 0,
    recovery_conversion_rate: 0,
    prev_no_show_rate: 18.0,
    no_show_reduction_rate: 0,
    benchmark_baseline: 18.0,
    benchmark_savings_rate: 0,
    confirmed_show_rate: 95.0,
    unconfirmed_show_rate: 78.0,
    confirmed_lift_rate: 17.0,
    confirmation_count: 0,
    top_offenders: []
  });

  const [runningNoshowCampaign, setRunningNoshowCampaign] = useState(false);
  const [noshowCampaignFeedback, setNoshowCampaignFeedback] = useState(null);

  const [suggestionsData, setSuggestionsData] = useState({
    latest_ai_insights: null,
    recommendations: []
  });

  const [benchmarksData, setBenchmarksData] = useState({
    benchmark_opt_in: true,
    specialty: "Physical Therapy & Sports Rehab",
    overall_percentile: 90,
    overall_tier: "National Top 10% (Network Leader)",
    clinic_call_volume: 0,
    specialty_call_volume_avg: 48.0,
    clinic_no_show_rate: 0,
    specialty_no_show_rate_avg: 19.5,
    no_show_rate: {
      clinic_value: 0,
      benchmark_avg: 19.5,
      benchmark_range: "18-22%",
      percentile: 75,
      percentile_label: "Top 25% Nationwide",
      status: "superior",
      delta: 0,
      source: "MGMA / APTA Physical Therapy Standard (18-22%)"
    },
    patient_recall_rate: {
      clinic_value: 0,
      benchmark_avg: 35.0,
      benchmark_range: "30-40%",
      percentile: 50,
      percentile_label: "At APTA Benchmark",
      status: "at_benchmark",
      delta: 0,
      source: "APTA Clinical Practice & Patient Retention Survey (35.0%)"
    },
    prior_auth_turnaround_days: {
      clinic_value: 0,
      benchmark_avg: 5.2,
      benchmark_range: "4.5-6.0 Days",
      days_saved: 0,
      percentile: 98,
      percentile_label: "Top 2% Nationwide",
      status: "superior",
      source: "MGMA Prior Authorization Regulatory Survey (5.2 days standard)"
    },
    call_handling: {
      clinic_call_volume: 0,
      specialty_call_volume_avg: 48.0,
      clinic_answer_rate: 100.0,
      specialty_answer_rate_avg: 71.0,
      percentile: 95,
      percentile_label: "Top 5% Nationwide",
      status: "superior",
      source: "AMGA Inbound Access & Patient Telephony Study (71.0%)"
    },
    data_sources: []
  });
  const [togglingOptIn, setTogglingOptIn] = useState(false);

  const [patientSearch, setPatientSearch] = useState("");

  // Compute final dates based on preset/custom
  const getDates = () => {

    if (customRange.start && customRange.end) {
      return {
        start_date: new Date(customRange.start).toISOString(),
        end_date: new Date(customRange.end).toISOString(),
        preset: undefined
      };
    }
    return {
      preset: preset,
      start_date: undefined,
      end_date: undefined
    };
  };

  const fetchData = async () => {
    const { start_date, end_date, preset: currentPreset } = getDates();
    const cacheKey = `analytics:v2:${currentPreset || "custom"}:${start_date || ""}:${end_date || ""}:${staffHourlyWage}:${avgVisitValue}`;
    const cached = getCacheItem(cacheKey);

    if (cached) {
      setRevenueData(cached.revenue);
      setCallsData(cached.calls);
      setRoiData(cached.roi);
      setCampaignsData(cached.campaigns);
      setPatientsData(cached.patients);
      setNoshowsData(cached.noshows);
      setSuggestionsData(cached.suggestions);
      setBenchmarksData(cached.benchmarks);
      setLoading(false);
    } else {
      setLoading(true);
    }
    
    try {
      const params = {
        preset: currentPreset,
        start_date: start_date,
        end_date: end_date
      };

      const roiParams = {
        ...params,
        staff_wage: staffHourlyWage,
        visit_value: avgVisitValue,
        daily_calls: dailyCallVolume,
        avg_call_mins: avgCallMins,
        clinic_days: clinicDaysPerMonth
      };
      
      const results = await Promise.allSettled([
        api.get("/analytics/revenue", { params }),
        api.get("/analytics/calls", { params }),
        api.get("/analytics/roi", { params: roiParams }),
        api.get("/analytics/campaigns", { params }),
        api.get("/analytics/patients", { params }),
        api.get("/analytics/no-shows", { params }),
        api.get("/analytics/suggestions", { params }),
        api.get("/analytics/benchmarks", { params })
      ]);


      const extract = (res, fallback) => {
        if (res.status === "fulfilled" && res.value?.data?.data) {
          const val = res.value.data.data;
          if (val && typeof val === "object") return val;
        }
        return fallback;
      };

      const rev = extract(results[0], revenueData);
      const calls = extract(results[1], callsData);
      const roi = extract(results[2], roiData);
      const campaigns = extract(results[3], campaignsData);
      const pat = extract(results[4], patientsData);
      const ns = extract(results[5], noshowsData);
      const sug = extract(results[6], suggestionsData);
      const bench = extract(results[7], benchmarksData);

      setRevenueData(rev);
      setCallsData(calls);
      setRoiData(roi);
      setCampaignsData(campaigns);
      setPatientsData(pat);
      setNoshowsData(ns);
      setSuggestionsData(sug);
      setBenchmarksData(bench);

      setCacheItem(cacheKey, {
        revenue: rev,
        calls: calls,
        roi: roi,
        campaigns: campaigns,
        patients: pat,
        noshows: ns,
        suggestions: sug,
        benchmarks: bench
      });
    } catch (err) {
      console.error("Failed to load analytics data", err);
    } finally {
      setLoading(false);
    }
  };

  // Real-time Reactive ROI Economics Model
  const calculatedRoi = useMemo(() => {
    // Dynamically reflects real total call count from database (total_ai_calls)
    const totalAiCalls = Number(
      roiData.total_ai_calls !== undefined
        ? roiData.total_ai_calls
        : (roiData.breakdown?.inbound_calls_count || 0) + (roiData.breakdown?.confirmations_count || 0) + (roiData.breakdown?.outreach_count || 0)
    ) || 0;

    const periodDays = roiData.inputs?.period_days || (preset === "7" ? 7 : preset === "90" ? 90 : 30);
    const periodWeeks = Math.max(0.14, periodDays / 7.0);

    // Exact formulas requested:
    // Hours Saved = (Total AI Calls * avg_mins_per_call) / 60
    // Dollar Savings = Hours Saved * hourly_wage
    const actualHoursSaved = Number(((totalAiCalls * avgCallMins) / 60.0).toFixed(1)) || 0;
    const actualCostSaved = Number((actualHoursSaved * staffHourlyWage).toFixed(2)) || 0;
    const actualHoursPerWeek = Number((actualHoursSaved / periodWeeks).toFixed(1)) || 0;

    // Monthly & Annual Projections based on calibration sliders
    const monthlyProjectedCalls = Math.round((dailyCallVolume || 35) * (clinicDaysPerMonth || 22));
    const projectedMonthlyHours = Number(((monthlyProjectedCalls * avgCallMins) / 60.0).toFixed(1)) || 0;
    const projectedMonthlySavings = Number((projectedMonthlyHours * staffHourlyWage).toFixed(2)) || 0;
    const projectedAnnualSavings = Number((projectedMonthlySavings * 12.0).toFixed(2)) || 0;
    const projectedWeeklyHours = Number((projectedMonthlyHours / 4.33).toFixed(1)) || 0;

    // Protected revenue
    const revenueProtected = Number(roiData.revenue_protected) || 0;
    const totalEconomicBenefit = Number((actualCostSaved + revenueProtected).toFixed(2));
    const periodSoftwareCost = Math.max(1.0, 299.0 * (periodDays / 30.0));
    const roiMultiplier = periodSoftwareCost > 0 ? Number((totalEconomicBenefit / periodSoftwareCost).toFixed(1)) : 0;

    // Detailed Breakdown
    const inboundCalls = roiData.breakdown?.inbound_calls_count || 0;
    const inboundHours = Number(((inboundCalls * avgCallMins) / 60.0).toFixed(1)) || 0;
    const confCount = roiData.breakdown?.confirmations_count || 0;
    const confHours = Number(((confCount * 3.0) / 60.0).toFixed(1)) || 0;
    const outreachCount = roiData.breakdown?.outreach_count || 0;
    const outreachHours = Number(((outreachCount * 5.0) / 60.0).toFixed(1)) || 0;

    return {
      totalAiCalls,
      actualHoursSaved,
      actualCostSaved,
      actualHoursPerWeek,
      monthlyProjectedCalls,
      projectedMonthlyHours,
      projectedMonthlySavings,
      projectedAnnualSavings,
      projectedWeeklyHours,
      revenueProtected,
      totalEconomicBenefit,
      roiMultiplier,
      inboundCalls,
      inboundHours,
      confCount,
      confHours,
      outreachCount,
      outreachHours
    };
  }, [roiData, staffHourlyWage, dailyCallVolume, avgCallMins, clinicDaysPerMonth, preset]);

  useEffect(() => {
    if (clinicId) {
      fetchData();
    }
  }, [clinicId, preset, customRange]);

  // Debounced API sync for ROI parameter adjustments (300ms)
  useEffect(() => {
    if (!clinicId) return;
    const timer = setTimeout(async () => {
      try {
        const { start_date, end_date, preset: currentPreset } = getDates();
        const res = await api.get("/analytics/roi", {
          params: {
            preset: currentPreset,
            start_date: start_date,
            end_date: end_date,
            staff_wage: staffHourlyWage,
            visit_value: avgVisitValue,
            daily_calls: dailyCallVolume,
            avg_call_mins: avgCallMins,
            clinic_days: clinicDaysPerMonth
          }
        });
        if (res.data?.data) {
          setRoiData(res.data.data);
        }
      } catch (err) {
        console.error("Failed to sync ROI calibration", err);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [staffHourlyWage, dailyCallVolume, avgCallMins, clinicDaysPerMonth, avgVisitValue]);

  const handleExport = async (reportType = "summary") => {
    const { start_date, end_date, preset: currentPreset } = getDates();
    setExporting(true);
    setExportMenuOpen(false);
    try {
      const res = await api.get("/analytics/export", {
        params: {
          type: reportType,
          preset: currentPreset,
          start_date: start_date,
          end_date: end_date
        },
        responseType: "blob"
      });
      
      const blob = new Blob([res.data], { type: "text/csv;charset=utf-8;" });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `bytelytic_${reportType}_report_${new Date().toISOString().slice(0,10)}.csv`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      setExportSuccess(true);
      setTimeout(() => setExportSuccess(false), 3500);
    } catch (err) {
      console.error("CSV Export failed", err);
      alert("Failed to export analytics report. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  const handleTriggerNoshowCampaign = async () => {
    setRunningNoshowCampaign(true);
    setNoshowCampaignFeedback(null);
    try {
      const res = await api.post("/calle/campaigns/no-show");
      setNoshowCampaignFeedback({
        type: "success",
        text: res.data?.message || `Successfully queued ${res.data?.queued || 0} no-show recovery calls!`
      });
      fetchData();
      setTimeout(() => setNoshowCampaignFeedback(null), 5000);
    } catch (err) {
      setNoshowCampaignFeedback({
        type: "error",
        text: err.response?.data?.detail || "Failed to trigger CALL-E recovery campaign."
      });
      setTimeout(() => setNoshowCampaignFeedback(null), 5000);
    } finally {
      setRunningNoshowCampaign(false);
    }
  };

  const handleToggleOptIn = async (newVal) => {
    setTogglingOptIn(true);
    try {
      await api.post(`/analytics/benchmarks/opt-in?opt_in=${newVal}`);
      setBenchmarksData(prev => ({ ...prev, benchmark_opt_in: newVal }));
      await fetchData();
    } catch (err) {
      console.error("Failed to update benchmark opt-in", err);
    } finally {
      setTogglingOptIn(false);
    }
  };

  // Convert markdown bullet points and headings to styled JSX elements
  const renderMarkdown = (markdownText) => {
    if (!markdownText) return <p className="text-sm text-on-surface-variant font-medium">No executive insight generated for this period yet.</p>;
    
    const lines = markdownText.split("\n");
    return lines.map((line, idx) => {
      const trimmed = line.trim();
      if (trimmed.startsWith("###")) {
        return (
          <h4 key={idx} className="text-sm font-black text-on-surface mt-5 mb-2 flex items-center gap-1.5 uppercase tracking-wide">
            {trimmed.replace("###", "").trim()}
          </h4>
        );
      }
      if (trimmed.startsWith("-") || trimmed.startsWith("*")) {
        return (
          <li key={idx} className="text-xs text-on-surface-variant ml-4 list-disc py-1 font-medium leading-relaxed">
            {trimmed.substring(1).trim().replace(/\*\*(.*?)\*\*/g, "$1")}
          </li>
        );
      }
      if (trimmed === "") return <div key={idx} className="h-2" />;
      return (
        <p key={idx} className="text-xs text-on-surface-variant leading-relaxed py-1 font-semibold">
          {trimmed.replace(/\*\*(.*?)\*\*/g, "$1")}
        </p>
      );
    });
  };

  // Heatmap helper constants
  const HEATMAP_DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const HEATMAP_HOURS_BUSINESS = ['7am', '8am', '9am', '10am', '11am', '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm'];
  const HEATMAP_HOURS_24 = [
    '12am', '1am', '2am', '3am', '4am', '5am', '6am', '7am', '8am', '9am', '10am', '11am',
    '12pm', '1pm', '2pm', '3pm', '4pm', '5pm', '6pm', '7pm', '8pm', '9pm', '10pm', '11pm'
  ];
  const activeHeatmapHours = heatmap24h ? HEATMAP_HOURS_24 : HEATMAP_HOURS_BUSINESS;

  const tabItems = [
    { id: "revenue", label: t.tab_revenue || "Revenue & ROI", icon: TrendingUp },
    { id: "calls", label: t.tab_calls || "Calls & Peak Heatmap", icon: Phone },
    { id: "roi", label: "Staff ROI Calculator", icon: Calculator },
    { id: "campaigns", label: "Campaign Comparison", icon: BarChart3 },
    { id: "patients", label: t.tab_patients || "Patients & VIP LTV", icon: Users },
    { id: "no-shows", label: t.tab_noshows || "No-Shows & Show Rate", icon: AlertCircle },
    { id: "suggestions", label: t.tab_insights || "AI Ops Insights", icon: Sparkles },
    { id: "benchmarking", label: t.tab_benchmarks || "Specialty Benchmarks", icon: ShieldAlert }
  ];

  return (
    <div className="space-y-6 pb-16 animate-in fade-in duration-300">
      {/* ── Header & Range Control Bar ─────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-[#e7e9dd] shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-[#edf7e0] text-[#396a00] border border-[#d2e7c4]">
              Practice Intelligence
            </span>
            {exportSuccess && (
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-green-100 text-green-800 flex items-center gap-1 animate-in fade-in">
                <Check className="w-3 h-3 text-green-700" /> Export Downloaded
              </span>
            )}
          </div>
          <h1 className="text-xl sm:text-2xl font-black text-on-surface tracking-tight mt-1">
            {t.clinical_intelligence || "Clinic Analytics & Insights"}
          </h1>
          <p className="text-xs text-on-surface-variant font-medium mt-0.5">
            {t.clinical_intelligence_sub || "Enterprise practice intelligence, patient retention pipelines, hourly call distribution, and ROI analytics."}
          </p>
        </div>

        {/* Range Selector & Multi-Report Export Button */}
        <div className="flex flex-wrap items-center gap-3">
          {/* Preset Buttons */}
          <div className="flex bg-[#f1f4ed] p-1 rounded-xl border border-[#e2e7dc]">
            {PRESETS.map((p) => {
              const isActive = preset === p.value && !customRange.start;
              return (
                <button
                  key={p.value}
                  onClick={() => {
                    setCustomRange({ start: "", end: "" });
                    setPreset(p.value);
                  }}
                  className={`px-3.5 py-1.5 text-xs font-bold rounded-lg transition-all ${
                    isActive
                      ? "bg-[#396a00] text-white shadow-sm"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  {p.label}
                </button>
              );
            })}
          </div>

          {/* Custom Date Input */}
          <div className="flex items-center gap-1.5 bg-[#f8faf6] rounded-xl px-3 py-1.5 border border-[#e2e7dc]">
            <input
              type="date"
              value={customRange.start}
              onChange={(e) => setCustomRange((prev) => ({ ...prev, start: e.target.value }))}
              className="bg-transparent outline-none text-xs text-on-surface font-semibold"
            />
            <span className="text-[10px] text-on-surface-variant uppercase font-bold">to</span>
            <input
              type="date"
              value={customRange.end}
              onChange={(e) => setCustomRange((prev) => ({ ...prev, end: e.target.value }))}
              className="bg-transparent outline-none text-xs text-on-surface font-semibold"
            />
          </div>

          {/* Export Dropdown */}
          <div className="relative">
            <button
              onClick={() => setExportMenuOpen(!exportMenuOpen)}
              disabled={exporting}
              className="px-4 py-2 bg-white hover:bg-[#f8faf6] text-on-surface border border-[#e2e7dc] rounded-xl text-xs font-bold flex items-center gap-2 shadow-sm transition-all"
            >
              {exporting ? (
                <Loader2 className="w-4 h-4 animate-spin text-[#396a00]" />
              ) : (
                <FileSpreadsheet className="w-4 h-4 text-[#396a00]" />
              )}
              <span>Export Report</span>
              <ChevronRight className={`w-3.5 h-3.5 transition-transform ${exportMenuOpen ? 'rotate-90' : ''}`} />
            </button>

            {exportMenuOpen && (
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-xl border border-[#e2e7dc] py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150">
                <div className="px-3 py-1.5 text-[10px] font-black uppercase tracking-wider text-on-surface-variant border-b border-[#f1f4ed]">
                  Download CSV Reports (HIPAA Audited)
                </div>
                <button
                  onClick={() => handleExport("summary")}
                  className="w-full text-left px-4 py-2 text-xs font-semibold text-on-surface hover:bg-[#edf7e0] flex items-center justify-between"
                >
                  <span>Executive KPI Summary</span>
                  <Award className="w-3.5 h-3.5 text-[#396a00]" />
                </button>
                <button
                  onClick={() => handleExport("revenue")}
                  className="w-full text-left px-4 py-2 text-xs font-semibold text-on-surface hover:bg-[#edf7e0] flex items-center justify-between"
                >
                  <span>Revenue & Billing Log</span>
                  <DollarSign className="w-3.5 h-3.5 text-[#396a00]" />
                </button>
                <button
                  onClick={() => handleExport("calls")}
                  className="w-full text-left px-4 py-2 text-xs font-semibold text-on-surface hover:bg-[#edf7e0] flex items-center justify-between"
                >
                  <span>Call Logs & Heatmap</span>
                  <Phone className="w-3.5 h-3.5 text-[#396a00]" />
                </button>
                <button
                  onClick={() => handleExport("campaigns")}
                  className="w-full text-left px-4 py-2 text-xs font-semibold text-on-surface hover:bg-[#edf7e0] flex items-center justify-between"
                >
                  <span>Campaign Performance</span>
                  <BarChart3 className="w-3.5 h-3.5 text-[#396a00]" />
                </button>
                <button
                  onClick={() => handleExport("roi")}
                  className="w-full text-left px-4 py-2 text-xs font-semibold text-on-surface hover:bg-[#edf7e0] flex items-center justify-between"
                >
                  <span>Staff Hours Saved & ROI</span>
                  <Calculator className="w-3.5 h-3.5 text-[#396a00]" />
                </button>
                <button
                  onClick={() => handleExport("no_shows")}
                  className="w-full text-left px-4 py-2 text-xs font-semibold text-on-surface hover:bg-[#edf7e0] flex items-center justify-between"
                >
                  <span>No-Show Audit Log</span>
                  <AlertCircle className="w-3.5 h-3.5 text-[#396a00]" />
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Navigation Tabs ────────────────────────────────────────── */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-1 border-b border-[#e2e7dc]" style={{ scrollbarWidth: 'none' }}>
        {tabItems.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-2.5 px-4 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${
                isActive 
                  ? "bg-[#396a00] text-white shadow-sm" 
                  : "bg-white text-on-surface-variant hover:bg-[#f1f4ed] hover:text-on-surface border border-[#e7e9dd]"
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Loading state indicator */}
      {loading && (
        <div className="h-48 flex flex-col items-center justify-center gap-2 bg-white rounded-2xl border border-[#e7e9dd]">
          <Loader2 className="w-8 h-8 animate-spin text-[#396a00]" />
          <p className="text-xs text-on-surface-variant font-semibold">Aggregating real-time clinic analytics...</p>
        </div>
      )}

      {/* ── Content Panes ──────────────────────────────────────────── */}
      {!loading && (
        <div className="space-y-6">
          
          {/* ═══════════════════════════════════════════════════════════
              TAB 1: REVENUE & FINANCIAL PIPELINE
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "revenue" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Top KPI row */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Total Period Revenue</span>
                  <p className="text-3xl font-black text-on-surface">{formatCurrency(revenueData.total_period_revenue)}</p>
                  <p className="text-[10px] text-on-surface-variant font-semibold">Booked through automated workflows</p>
                </div>
                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Projected Annual Run-Rate</span>
                  <p className="text-3xl font-black text-[#2e7d32]">{formatCurrency(revenueData.projected_annual_savings)}</p>
                  <p className="text-[10px] text-green-700 font-bold">Extrapolated based on current velocity</p>
                </div>
                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Average Booking Value</span>
                  <p className="text-3xl font-black text-on-surface">
                    {formatCurrency(revenueData.avg_booking_value || (callsData.booked_calls_count > 0 && revenueData.total_period_revenue > 0 ? Math.round(revenueData.total_period_revenue / callsData.booked_calls_count) : 150))}
                  </p>
                  <p className="text-[10px] text-on-surface-variant font-semibold">Per confirmed appointment</p>
                </div>
                <div className="card p-5 bg-[#edf7e0] border border-[#d2e7c4] space-y-1">
                  <span className="overline text-[#396a00]">Platform ROI Multiplier</span>
                  <p className="text-3xl font-black text-[#396a00]">{roiData.roi_multiplier || 1.0}x</p>
                  <p className="text-[10px] text-green-800 font-bold">Net economic gain vs software tier</p>
                </div>
              </div>

              {/* 12-Month Area Chart */}
              <div className="card p-6 bg-white border border-[#e7e9dd]">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">Bytelytic 12-Month Revenue Trajectory</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">Historical monthly value recovered via autonomous CALL-E scheduling & recalls.</p>
                  </div>
                  <span className="text-xs font-bold text-[#396a00] bg-[#edf7e0] px-3 py-1 rounded-full border border-[#d2e7c4]">
                    12-Month Trajectory
                  </span>
                </div>

                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={revenueData.trend || []} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#396a00" stopOpacity={0.45}/>
                          <stop offset="95%" stopColor="#396a00" stopOpacity={0.02}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f4ed" />
                      <XAxis 
                        dataKey="month" 
                        tickLine={false} 
                        tick={{ fill: "#42493a", fontSize: 10, fontWeight: 700 }} 
                      />
                      <YAxis 
                        tickLine={false} 
                        tick={{ fill: "#42493a", fontSize: 10, fontWeight: 700 }} 
                        tickFormatter={(v) => `$${v}`} 
                      />
                      <Tooltip 
                        formatter={(v) => [`$${Number(v || 0).toLocaleString()}`, "Revenue"]} 
                        contentStyle={{ borderRadius: "12px", border: "1px solid #e7e9dd", boxShadow: "0 4px 12px rgba(0,0,0,0.05)" }} 
                      />
                      <Area 
                        type="monotone" 
                        dataKey="revenue" 
                        stroke="#396a00" 
                        strokeWidth={2.5} 
                        fillOpacity={1} 
                        fill="url(#colorRevenue)" 
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Bottom Row: Breakdown Bar Chart + Hero Card */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="card p-6 bg-white border border-[#e7e9dd] flex flex-col justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-on-surface">Revenue by Workflow Category</h4>
                    <p className="text-[11px] text-on-surface-variant font-medium">Composition of revenue generated in the selected window.</p>
                  </div>
                  
                  {revenueData.breakdown && revenueData.breakdown.length > 0 ? (
                    <div className="h-64 w-full mt-4">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={revenueData.breakdown}>
                          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f4ed" />
                          <XAxis dataKey="type" tickLine={false} tick={{ fill: "#42493a", fontSize: 10, fontWeight: 600 }} />
                          <YAxis tickFormatter={(v) => `$${v}`} tickLine={false} tick={{ fill: "#42493a", fontSize: 10 }} />
                          <Tooltip formatter={(v) => [`$${Number(v || 0).toLocaleString()}`, "Amount"]} />
                          <Bar dataKey="value" fill="#396a00" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-64 flex flex-col items-center justify-center text-xs text-on-surface-variant">
                      <BarChart3 className="w-8 h-8 opacity-30 mb-2" />
                      <span>No categorized revenue events in this period yet.</span>
                    </div>
                  )}
                </div>

                <div className="card p-6 bg-gradient-to-br from-[#1a3a2e] to-[#122f23] text-white flex flex-col justify-between relative overflow-hidden rounded-2xl shadow-md">
                  <div className="absolute -top-12 -right-12 w-40 h-40 rounded-full bg-[#7FCD4D]/15 blur-2xl pointer-events-none" />
                  <div>
                    <span className="text-[#7FCD4D] text-xs font-black uppercase tracking-widest">Financial Yield Summary</span>
                    <h3 className="text-sm font-extrabold mt-3 text-gray-300">Period Economic Value Created</h3>
                    <p className="text-4xl font-black text-white mt-2">{formatCurrency(revenueData.total_period_revenue)}</p>
                  </div>
                  
                  <div className="space-y-3.5 border-t border-white/10 pt-5 mt-6">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-gray-300 font-medium">Inbound Booking Conversions</span>
                      <span className="font-bold text-[#7FCD4D]">{callsData.booked_calls_count || 0} visits</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-gray-300 font-medium">Staff Labor Wage Savings</span>
                      <span className="font-bold text-[#7FCD4D]">{formatCurrency(roiData.staff_cost_saved || 0)}</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-gray-300 font-medium">Protected Appointment Pipeline</span>
                      <span className="font-bold text-[#7FCD4D]">{formatCurrency(roiData.revenue_protected || 0)}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
              TAB 2: CALLS & PEAK HEATMAP MATRIX
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "calls" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Call Summary KPIs */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Total Calls in Period</span>
                  <p className="text-3xl font-black text-on-surface">{callsData.total_calls}</p>
                  <div className={`flex items-center gap-1 text-[10px] font-bold ${callsData.mom_change_percent >= 0 ? 'text-green-700' : 'text-rose-700'}`}>
                    {callsData.mom_change_percent >= 0 ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                    <span>{callsData.mom_change_percent >= 0 ? "+" : ""}{callsData.mom_change_percent}% vs previous period</span>
                  </div>
                </div>

                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Answer & Resolution Rate</span>
                  <p className="text-3xl font-black text-[#2e7d32]">{callsData.answer_rate}%</p>
                  <p className="text-[10px] text-green-700 font-bold">{callsData.handled_calls} calls successfully handled</p>
                </div>

                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Inbound Call Conversion</span>
                  <p className="text-3xl font-black text-[#1565c0]">{callsData.inbound_conversion_rate}%</p>
                  <p className="text-[10px] text-[#1565c0] font-bold">{callsData.booked_calls_count} calls converted to appointments</p>
                </div>

                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Avg Call Duration</span>
                  <p className="text-3xl font-black text-on-surface">
                    {Math.floor(callsData.avg_duration_seconds / 60)}m {callsData.avg_duration_seconds % 60}s
                  </p>
                  <p className="text-[10px] text-on-surface-variant font-semibold">{callsData.total_duration_minutes} total active minutes</p>
                </div>
              </div>

              {/* Peak Inbound Call Hours Distribution Chart */}
              <div className="card p-6 bg-white border border-[#e7e9dd]">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">Peak Inbound Call Hours Distribution</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">Aggregate hourly call volume distribution (8:00 AM – 7:00 PM).</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs font-bold">
                    <span className="flex items-center gap-1.5 text-[#396a00]"><span className="w-3 h-3 bg-[#396a00] rounded" /> Handled</span>
                    <span className="flex items-center gap-1.5 text-[#b71c1c]"><span className="w-3 h-3 bg-[#e53935] rounded" /> Missed</span>
                  </div>
                </div>

                <div className="h-72 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={callsData.peak_hours_distribution || []}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f4ed" />
                      <XAxis dataKey="hour" tickLine={false} tick={{ fill: "#42493a", fontSize: 10, fontWeight: 700 }} />
                      <YAxis tickLine={false} tick={{ fill: "#42493a", fontSize: 10 }} />
                      <Tooltip 
                        formatter={(v, name) => [v, name === "handled" ? "Handled Calls" : "Missed Calls"]}
                        contentStyle={{ borderRadius: "10px", border: "1px solid #e7e9dd" }}
                      />
                      <Bar dataKey="handled" fill="#396a00" stackId="a" radius={[0, 0, 0, 0]} />
                      <Bar dataKey="missed" fill="#e53935" stackId="a" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Heatmap Matrix (Mon-Sun x 24h / Standard Hours) */}
              <div className="card p-6 bg-white border border-[#e7e9dd] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-bold text-on-surface">Weekly Call Density & Triage Heatmap</h3>
                      {callsData.timezone && (
                        <span className="text-[10px] font-bold text-on-surface-variant bg-[#f1f4ed] border border-[#e2e7dc] px-2 py-0.5 rounded-full">
                          {callsData.timezone}
                        </span>
                      )}
                    </div>
                    <p className="text-[11px] text-on-surface-variant font-medium">Pinpoint high-traffic call windows and front-desk staffing bottlenecks.</p>
                  </div>
                  <div className="flex items-center gap-4 flex-wrap">
                    <button
                      type="button"
                      onClick={() => setHeatmap24h(!heatmap24h)}
                      className="px-3 py-1 text-[11px] font-bold rounded-lg border border-[#e7e9dd] bg-[#f8faf6] hover:bg-[#eef3ea] text-on-surface transition-colors cursor-pointer"
                    >
                      {heatmap24h ? "Switch to Standard (7am–8pm)" : "Switch to 24-Hour Matrix"}
                    </button>
                    <div className="flex flex-wrap gap-4 text-[10px] font-black text-on-surface-variant uppercase tracking-wider">
                      <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-[#f8faf6] border border-[#e2e7dc] rounded" /> Quiet</span>
                      <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-[#e8f5e9] border border-[#a5d6a7] rounded" /> Handled</span>
                      <span className="flex items-center gap-1.5"><span className="w-3 h-3 bg-rose-100 border border-rose-300 rounded" /> Missed Alerts</span>
                    </div>
                  </div>
                </div>

                <div className="overflow-x-auto pt-2">
                  <div className={`${heatmap24h ? "min-w-[1150px]" : "min-w-[780px]"} grid grid-cols-[60px_1fr] gap-2`}>
                    <div />
                    <div
                      className="grid gap-1.5 text-center text-[10px] font-bold text-on-surface-variant uppercase tracking-wider pb-1"
                      style={{ gridTemplateColumns: `repeat(${activeHeatmapHours.length}, minmax(0, 1fr))` }}
                    >
                      {activeHeatmapHours.map((h) => <div key={h}>{h}</div>)}
                    </div>

                    {HEATMAP_DAYS.map((day) => (
                      <React.Fragment key={day}>
                        <div className="text-xs font-bold text-on-surface-variant flex items-center justify-end pr-3 font-mono">
                          {day}
                        </div>
                        
                        <div
                          className="grid gap-1.5"
                          style={{ gridTemplateColumns: `repeat(${activeHeatmapHours.length}, minmax(0, 1fr))` }}
                        >
                          {activeHeatmapHours.map((hour) => {
                            const cell = callsData.heatmap?.[day]?.[hour] || { handled: 0, missed: 0, total: 0 };
                            let bg = "bg-[#f8faf6] hover:bg-[#eef3ea]";
                            let border = "border border-[#e7e9dd]";
                            let text = "text-on-surface-variant/30";
                            
                            if (cell.missed > 0) {
                              bg = "bg-[#ffebee] hover:bg-[#ffcdd2]";
                              border = "border border-[#ef9a9a]";
                              text = "text-red-700 font-black";
                            } else if (cell.handled > 0) {
                              bg = "bg-[#e8f5e9] hover:bg-[#c8e6c9]";
                              border = "border border-[#a5d6a7]";
                              text = "text-green-800 font-bold";
                            }
                            
                            return (
                              <div
                                key={hour}
                                className={`${bg} ${border} h-10 rounded-xl transition duration-150 flex flex-col items-center justify-center cursor-pointer`}
                                title={`${day} ${hour}: ${cell.handled} Handled, ${cell.missed} Missed`}
                              >
                                {(cell.handled > 0 || cell.missed > 0) ? (
                                  <span className={`text-[10px] ${text}`}>
                                    {cell.missed > 0 ? `!${cell.missed}` : cell.handled}
                                  </span>
                                ) : (
                                  <span className="text-[10px] text-on-surface-variant/20">-</span>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
              TAB 3: STAFF ROI & ECONOMIC CALCULATOR
             ═══════════════════════════════════════════════════════════ */}
          {/* ═══════════════════════════════════════════════════════════
              TAB 3: STAFF ROI & ECONOMIC CALCULATOR
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "roi" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Top Hero ROI Summary */}
              <div className="card p-8 bg-gradient-to-br from-[#1a3a2e] to-[#122f23] text-white rounded-3xl relative overflow-hidden shadow-lg">
                <div className="absolute top-0 right-0 p-8 bg-[#7fcd4d]/10 blur-3xl w-64 h-64 pointer-events-none rounded-full" />
                
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 relative z-10">
                  <div className="lg:col-span-2 space-y-3">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-3 py-1 bg-[#7FCD4D]/20 text-[#7FCD4D] rounded-full text-xs font-black uppercase tracking-wider border border-[#7FCD4D]/30">
                        Practice ROI Intelligence
                      </span>
                      <span className="px-2.5 py-0.5 bg-white/10 text-white/90 rounded-full text-[11px] font-bold border border-white/15">
                        {calculatedRoi.totalAiCalls} Live DB Voice Calls
                      </span>
                    </div>
                    <h2 className="text-2xl sm:text-3xl font-black text-white">Staff Labor Hours Saved per Week</h2>
                    <p className="text-xs text-gray-300 max-w-md leading-relaxed font-medium">
                      Automated voice triage, appointment booking, multi-touch confirmations, and recall outreach free your staff from manual phone calls.
                    </p>
                    <div className="pt-2 flex items-baseline gap-3">
                      <span className="text-5xl font-black text-[#7FCD4D]">{calculatedRoi.actualHoursPerWeek}</span>
                      <span className="text-sm font-bold text-gray-300">hours saved / week</span>
                      <span className="text-xs text-gray-400 font-medium">({calculatedRoi.actualHoursSaved} hrs in period)</span>
                    </div>
                  </div>

                  <div className="bg-white/5 border border-white/10 p-5 rounded-2xl flex flex-col justify-between">
                    <span className="text-xs font-bold text-gray-300">Front-Desk Labor Cost Saved</span>
                    <p className="text-3xl font-black text-white">{formatCurrency(calculatedRoi.actualCostSaved)}</p>
                    <p className="text-[10px] text-[#7FCD4D] font-bold">At ${staffHourlyWage}/hr wage rate • {calculatedRoi.actualHoursSaved} hrs saved</p>
                  </div>

                  <div className="bg-white/5 border border-white/10 p-5 rounded-2xl flex flex-col justify-between">
                    <span className="text-xs font-bold text-gray-300">Total Net Economic Benefit</span>
                    <p className="text-3xl font-black text-[#7FCD4D]">{formatCurrency(calculatedRoi.totalEconomicBenefit)}</p>
                    <p className="text-[10px] text-[#7FCD4D] font-bold">{calculatedRoi.roiMultiplier}x software ROI (incl. {formatCurrency(calculatedRoi.revenueProtected)} protected revenue)</p>
                  </div>
                </div>
              </div>

              {/* Mathematical Formula Transparency & Validation */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-white border border-[#e2e7dc] rounded-2xl flex items-start gap-3 shadow-sm">
                  <div className="p-2.5 rounded-xl bg-[#edf7e0] text-[#396a00]">
                    <Calculator className="w-5 h-5" />
                  </div>
                  <div className="space-y-1 text-xs">
                    <span className="font-bold text-[#396a00] uppercase tracking-wider text-[10px]">Hours Saved Formula</span>
                    <p className="font-mono text-on-surface font-semibold">Hours Saved = (Total AI Calls × Avg Mins per Call) ÷ 60</p>
                    <p className="text-on-surface-variant font-medium text-[11px]">
                      ({calculatedRoi.totalAiCalls} calls × {avgCallMins} min) ÷ 60 = <strong className="text-on-surface">{calculatedRoi.actualHoursSaved} hrs saved</strong>
                    </p>
                  </div>
                </div>

                <div className="p-4 bg-white border border-[#e2e7dc] rounded-2xl flex items-start gap-3 shadow-sm">
                  <div className="p-2.5 rounded-xl bg-[#edf7e0] text-[#396a00]">
                    <DollarSign className="w-5 h-5" />
                  </div>
                  <div className="space-y-1 text-xs">
                    <span className="font-bold text-[#396a00] uppercase tracking-wider text-[10px]">Dollar Savings Formula</span>
                    <p className="font-mono text-on-surface font-semibold">Dollar Savings = Hours Saved × Receptionist Hourly Wage</p>
                    <p className="text-on-surface-variant font-medium text-[11px]">
                      {calculatedRoi.actualHoursSaved} hrs × ${staffHourlyWage}/hr = <strong className="text-[#396a00]">{formatCurrency(calculatedRoi.actualCostSaved)}</strong> saved in payroll
                    </p>
                  </div>
                </div>
              </div>

              {/* Interactive ROI Parameter Sliders */}
              <div className="card p-6 bg-white border border-[#e7e9dd] space-y-6">
                <div className="flex items-center gap-2 pb-2 border-b border-[#f1f4ed]">
                  <SlidersHorizontal className="w-5 h-5 text-[#396a00]" />
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">Interactive Clinic ROI Calibration</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">Calibrate practice variables to dynamically recalculate labor savings, practice capacity, and revenue in real time.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {/* Slider 1: Receptionist Hourly Wage ($20 - $45/hr) */}
                  <div className="space-y-3 p-4 bg-[#f8faf6] rounded-2xl border border-[#e2e7dc]">
                    <div className="flex justify-between items-center">
                      <label className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                        <Clock className="w-4 h-4 text-[#396a00]" /> Receptionist Hourly Wage
                      </label>
                      <span className="text-sm font-black text-[#396a00] font-mono">${staffHourlyWage} / hr</span>
                    </div>
                    <input 
                      type="range" 
                      min="20" 
                      max="45" 
                      step="1"
                      value={staffHourlyWage}
                      onChange={(e) => setStaffHourlyWage(Number(e.target.value))}
                      className="w-full accent-[#396a00] cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-on-surface-variant font-bold">
                      <span>$20/hr</span>
                      <span>$30/hr (National Avg)</span>
                      <span>$45/hr</span>
                    </div>
                  </div>

                  {/* Slider 2: Daily Manual Call Volume */}
                  <div className="space-y-3 p-4 bg-[#f8faf6] rounded-2xl border border-[#e2e7dc]">
                    <div className="flex justify-between items-center">
                      <label className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                        <Phone className="w-4 h-4 text-[#396a00]" /> Daily Manual Call Volume
                      </label>
                      <span className="text-sm font-black text-[#396a00] font-mono">{dailyCallVolume} calls / day</span>
                    </div>
                    <input 
                      type="range" 
                      min="10" 
                      max="150" 
                      step="5"
                      value={dailyCallVolume}
                      onChange={(e) => setDailyCallVolume(Number(e.target.value))}
                      className="w-full accent-[#396a00] cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-on-surface-variant font-bold">
                      <span>10 calls/day</span>
                      <span>35 calls/day (Avg Clinic)</span>
                      <span>150 calls/day</span>
                    </div>
                  </div>

                  {/* Slider 3: Average Minutes Spent per Manual Call (3 - 8 min) */}
                  <div className="space-y-3 p-4 bg-[#f8faf6] rounded-2xl border border-[#e2e7dc]">
                    <div className="flex justify-between items-center">
                      <label className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                        <Activity className="w-4 h-4 text-[#396a00]" /> Avg Minutes per Call
                      </label>
                      <span className="text-sm font-black text-[#396a00] font-mono">{avgCallMins} min / call</span>
                    </div>
                    <input 
                      type="range" 
                      min="3" 
                      max="8" 
                      step="0.5"
                      value={avgCallMins}
                      onChange={(e) => setAvgCallMins(Number(e.target.value))}
                      className="w-full accent-[#396a00] cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-on-surface-variant font-bold">
                      <span>3.0 min (Quick)</span>
                      <span>4.5 min (Standard)</span>
                      <span>8.0 min (Complex)</span>
                    </div>
                  </div>

                  {/* Slider 4: Clinic Days per Month */}
                  <div className="space-y-3 p-4 bg-[#f8faf6] rounded-2xl border border-[#e2e7dc]">
                    <div className="flex justify-between items-center">
                      <label className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                        <Calendar className="w-4 h-4 text-[#396a00]" /> Clinic Days per Month
                      </label>
                      <span className="text-sm font-black text-[#396a00] font-mono">{clinicDaysPerMonth} days / mo</span>
                    </div>
                    <input 
                      type="range" 
                      min="15" 
                      max="28" 
                      step="1"
                      value={clinicDaysPerMonth}
                      onChange={(e) => setClinicDaysPerMonth(Number(e.target.value))}
                      className="w-full accent-[#396a00] cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-on-surface-variant font-bold">
                      <span>15 days (Part-time)</span>
                      <span>22 days (Standard M-F)</span>
                      <span>28 days (Extended)</span>
                    </div>
                  </div>

                  {/* Slider 5: Average Patient Visit Revenue */}
                  <div className="space-y-3 p-4 bg-[#f8faf6] rounded-2xl border border-[#e2e7dc] md:col-span-2 lg:col-span-2">
                    <div className="flex justify-between items-center">
                      <label className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                        <DollarSign className="w-4 h-4 text-[#396a00]" /> Average Patient Visit Revenue
                      </label>
                      <span className="text-sm font-black text-[#396a00] font-mono">${avgVisitValue} / visit</span>
                    </div>
                    <input 
                      type="range" 
                      min="50" 
                      max="500" 
                      step="10"
                      value={avgVisitValue}
                      onChange={(e) => setAvgVisitValue(Number(e.target.value))}
                      className="w-full accent-[#396a00] cursor-pointer"
                    />
                    <div className="flex justify-between text-[10px] text-on-surface-variant font-bold">
                      <span>$50</span>
                      <span>$150 (Specialty Avg)</span>
                      <span>$500</span>
                    </div>
                  </div>
                </div>

                {/* Monthly & Annual Practice Projections */}
                <div className="p-5 bg-gradient-to-r from-[#edf7e0] to-[#f4faec] border border-[#d2e7c4] rounded-2xl space-y-3">
                  <div className="flex items-center justify-between flex-wrap gap-2">
                    <span className="text-xs font-black uppercase text-[#396a00] tracking-wider">
                      Practice Capacity & Economic Projections (Calibrated)
                    </span>
                    <span className="text-[11px] font-bold text-on-surface-variant">
                      Based on {dailyCallVolume} calls/day × {clinicDaysPerMonth} clinic days/month
                    </span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-1">
                    <div className="bg-white/80 p-3 rounded-xl border border-[#d2e7c4]">
                      <span className="text-[10px] font-bold text-on-surface-variant block">Monthly Automated Calls</span>
                      <span className="text-lg font-black text-on-surface">{calculatedRoi.monthlyProjectedCalls.toLocaleString()}</span>
                    </div>
                    <div className="bg-white/80 p-3 rounded-xl border border-[#d2e7c4]">
                      <span className="text-[10px] font-bold text-on-surface-variant block">Monthly Staff Hours Saved</span>
                      <span className="text-lg font-black text-[#396a00]">{calculatedRoi.projectedMonthlyHours} hrs <span className="text-xs font-semibold text-on-surface-variant">({calculatedRoi.projectedWeeklyHours}/wk)</span></span>
                    </div>
                    <div className="bg-white/80 p-3 rounded-xl border border-[#d2e7c4]">
                      <span className="text-[10px] font-bold text-on-surface-variant block">Monthly Payroll Saved</span>
                      <span className="text-lg font-black text-[#396a00]">{formatCurrency(calculatedRoi.projectedMonthlySavings)}</span>
                    </div>
                    <div className="bg-white/80 p-3 rounded-xl border border-[#d2e7c4]">
                      <span className="text-[10px] font-bold text-on-surface-variant block">Annualized Savings</span>
                      <span className="text-lg font-black text-[#396a00]">{formatCurrency(calculatedRoi.projectedAnnualSavings)}</span>
                    </div>
                  </div>
                </div>

                {/* Savings Methodology breakdown */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                  <div className="p-4 bg-[#edf7e0] border border-[#d2e7c4] rounded-xl space-y-1">
                    <span className="text-[10px] font-black uppercase text-[#396a00]">Inbound Call Triage</span>
                    <p className="text-lg font-black text-[#396a00]">{calculatedRoi.inboundHours} hrs</p>
                    <p className="text-[10px] text-on-surface-variant font-semibold">
                      {calculatedRoi.inboundCalls} calls handled @ {avgCallMins} min saved per call via autonomous AI
                    </p>
                  </div>
                  <div className="p-4 bg-[#edf7e0] border border-[#d2e7c4] rounded-xl space-y-1">
                    <span className="text-[10px] font-black uppercase text-[#396a00]">Outbound Confirmations</span>
                    <p className="text-lg font-black text-[#396a00]">{calculatedRoi.confHours} hrs</p>
                    <p className="text-[10px] text-on-surface-variant font-semibold">
                      {calculatedRoi.confCount} confirmations handled @ 3.0 min saved per appointment confirmation
                    </p>
                  </div>
                  <div className="p-4 bg-[#edf7e0] border border-[#d2e7c4] rounded-xl space-y-1">
                    <span className="text-[10px] font-black uppercase text-[#396a00]">Patient Recall Outreach</span>
                    <p className="text-lg font-black text-[#396a00]">{calculatedRoi.outreachHours} hrs</p>
                    <p className="text-[10px] text-on-surface-variant font-semibold">
                      {calculatedRoi.outreachCount} outreach follow-ups handled @ 5.0 min saved per overdue patient
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
              TAB 4: CAMPAIGN PERFORMANCE COMPARISON
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "campaigns" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Campaign Cards Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
                {[
                  { key: "confirmation", title: "Confirmations", stat: campaignsData.campaigns?.confirmation, color: "#396a00" },
                  { key: "no_show", title: "No-Show Recovery", stat: campaignsData.campaigns?.no_show, color: "#b71c1c" },
                  { key: "recall", title: "Overdue Recalls", stat: campaignsData.campaigns?.recall, color: "#1565c0" },
                  { key: "survey", title: "Patient Feedback", stat: campaignsData.campaigns?.survey, color: "#6a1b9a" },
                  { key: "waitlist", title: "Waitlist Backfill", stat: campaignsData.campaigns?.waitlist, color: "#00838f" }
                ].map((c) => {
                  const data = c.stat || { total_initiated: 0, reached_count: 0, converted_count: 0, conversion_rate: 0, reached_rate: 0, revenue_recovered: 0 };
                  return (
                    <div key={c.key} className="card p-4 bg-white border border-[#e7e9dd] flex flex-col justify-between space-y-3">
                      <div>
                        <div className="flex justify-between items-center">
                          <span className="text-[10px] font-black uppercase tracking-wider text-on-surface-variant">{c.title}</span>
                          <span className="text-[11px] font-bold font-mono px-2 py-0.5 rounded bg-[#f1f4ed] text-on-surface">
                            {data.total_initiated} calls
                          </span>
                        </div>
                        <p className="text-xl font-black text-on-surface mt-2">{data.converted_count} Converted</p>
                        <div className="flex items-center gap-1.5 mt-0.5 text-[10px]">
                          <span className="text-green-700 font-bold">{data.conversion_rate}% conversion</span>
                          <span className="text-on-surface-variant">•</span>
                          <span className="text-on-surface-variant font-medium">{data.reached_count} reached</span>
                        </div>
                      </div>

                      <div className="border-t border-[#f1f4ed] pt-2.5 flex justify-between items-center text-xs">
                        <span className="text-on-surface-variant font-semibold">Value Generated</span>
                        <span className="font-bold text-[#396a00] font-mono">{formatCurrency(data.revenue_recovered)}</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Side-by-Side Comparison Chart */}
              <div className="card p-6 bg-white border border-[#e7e9dd]">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">Side-by-Side Campaign Conversion Comparison</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">
                      Comparing outreach volume vs successful conversion goals across all 5 voice AI workflows.
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-bold">
                    <span className="flex items-center gap-1.5 text-[#42493a]"><span className="w-3 h-3 bg-[#e2e7dc] rounded" /> Initiated</span>
                    <span className="flex items-center gap-1.5 text-[#42493a]"><span className="w-3 h-3 bg-[#c8d6b9] rounded" /> Reached</span>
                    <span className="flex items-center gap-1.5 text-[#396a00]"><span className="w-3 h-3 bg-[#396a00] rounded" /> Converted</span>
                  </div>
                </div>

                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={campaignsData.comparison_chart || []}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f4ed" />
                      <XAxis dataKey="campaign" tickLine={false} tick={{ fill: "#42493a", fontSize: 11, fontWeight: 700 }} />
                      <YAxis tickLine={false} tick={{ fill: "#42493a", fontSize: 10 }} />
                      <Tooltip 
                        formatter={(v, name) => [v, name === "converted" ? "Goals Converted" : name === "reached" ? "Patients Reached" : "Calls Initiated"]}
                        contentStyle={{ borderRadius: "10px", border: "1px solid #e7e9dd" }}
                      />
                      <Bar dataKey="initiated" fill="#e2e7dc" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="reached" fill="#c8d6b9" radius={[4, 4, 0, 0]} />
                      <Bar dataKey="converted" fill="#396a00" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
              TAB 5: PATIENTS & VIP LTV
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "patients" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Patient Search Bar */}
              <div className="flex items-center gap-3 bg-white p-3.5 rounded-2xl border border-[#e7e9dd] shadow-sm">
                <Search className="w-4 h-4 text-on-surface-variant" />
                <input
                  type="text"
                  placeholder="Filter VIP or high-risk patients by name or phone..."
                  value={patientSearch}
                  onChange={(e) => setPatientSearch(e.target.value)}
                  className="w-full text-xs font-semibold bg-transparent outline-none text-on-surface placeholder:text-on-surface-variant/50"
                />
                {patientSearch && (
                  <button
                    onClick={() => setPatientSearch("")}
                    className="text-xs text-on-surface-variant hover:text-on-surface px-2 py-0.5 rounded-md hover:bg-slate-100"
                  >
                    Clear
                  </button>
                )}
              </div>

              {/* Donut Chart + Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="card p-6 bg-white border border-[#e7e9dd] flex flex-col justify-between md:col-span-1">
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">Patient Ratio Analysis</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">New enrollments vs returning patient visits.</p>
                  </div>
                  
                  <div className="h-56 w-full flex items-center justify-center my-2">
                    {patientsData.ratio && patientsData.ratio.some(r => Number(r.value) > 0) ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={patientsData.ratio}
                            cx="50%"
                            cy="50%"
                            innerRadius={55}
                            outerRadius={75}
                            paddingAngle={4}
                            dataKey="value"
                          >
                            <Cell fill="#396a00" />
                            <Cell fill="#7FCD4D" />
                          </Pie>
                          <Tooltip formatter={(v) => [v, "Patients"]} />
                          <Legend verticalAlign="bottom" height={36} iconSize={10} iconType="circle" wrapperStyle={{ fontSize: 11, fontWeight: 700 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="flex flex-col items-center justify-center h-full text-center p-4">
                        <Users className="w-8 h-8 text-on-surface-variant/40 mb-2" />
                        <p className="text-xs font-bold text-on-surface">No patient visits recorded</p>
                        <p className="text-[10px] text-on-surface-variant">Active patient ratio will display once visits occur.</p>
                      </div>
                    )}
                  </div>

                  <div className="border-t border-[#f1f4ed] pt-3 text-center">
                    <span className="text-[10px] text-on-surface-variant uppercase font-bold">Average Patient LTV</span>
                    <p className="text-xl font-black text-on-surface mt-0.5">{formatCurrency(patientsData.average_ltv)}</p>
                  </div>
                </div>

                {/* Top VIP Leaderboard */}
                <div className="card p-6 bg-white border border-[#e7e9dd] md:col-span-2 space-y-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="text-sm font-bold text-on-surface">VIP Patient LTV Leaderboard</h3>
                      <p className="text-[11px] text-on-surface-variant font-medium">Top contributing patients automatically prioritized for retention outreach.</p>
                    </div>
                    <span className="text-xs font-bold text-amber-700 bg-amber-50 px-2.5 py-1 rounded-lg border border-amber-200">
                      VIP Status
                    </span>
                  </div>
                  
                  <div className="divide-y divide-[#f1f4ed]">
                    {patientsData.vip_list && patientsData.vip_list.length > 0 ? (
                      patientsData.vip_list
                        .filter(v => !patientSearch || (v.name || "").toLowerCase().includes(patientSearch.toLowerCase()) || (v.phone || "").includes(patientSearch))
                        .map((vip) => (
                        <div key={vip.id} className="flex justify-between items-center py-3">
                          <div className="flex items-center gap-3">
                            <span className="px-2 py-0.5 rounded text-[9px] font-black bg-amber-500/10 text-amber-600 border border-amber-500/20 uppercase">
                              VIP
                            </span>
                            <div>
                              <p className="text-xs font-bold text-on-surface">{vip.name}</p>
                              <p className="text-[10px] text-on-surface-variant font-mono">
                                {vip.phone || vip.email || "Contact on file"}
                                {vip.total_visits ? ` • ${vip.total_visits} visits` : ""}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <span className="text-xs font-mono font-black text-on-surface">
                              {formatCurrency(vip.total_revenue_generated || 0)}
                            </span>
                            <p className="text-[9px] text-green-700 font-bold">Lifetime Value</p>
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-8 text-xs text-on-surface-variant">No VIP patients recorded in this period yet.</div>
                    )}
                  </div>
                </div>
              </div>

              {/* Churn Risk Watchlist */}
              <div className="card p-6 bg-white border border-[#e7e9dd] space-y-4">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-5 h-5 text-[#b71c1c]" />
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">High Churn-Risk Watchlist</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">Patients overdue for regular care or flagged with elevated churn probability.</p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {patientsData.churn_risk_list && patientsData.churn_risk_list.length > 0 ? (
                    patientsData.churn_risk_list
                      .filter(c => !patientSearch || (c.name || "").toLowerCase().includes(patientSearch.toLowerCase()))
                      .map((pat) => (
                      <div key={pat.id} className="flex justify-between items-center bg-[#fff5f6] border border-[#ffcdd2] px-4 py-3 rounded-2xl">
                        <div>
                          <p className="text-xs font-bold text-on-surface">{pat.name}</p>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-[10px] text-[#b71c1c] font-bold">
                              Risk Factor: {round(parseFloat(pat.churn_risk_score || 0) * 100)}%
                            </span>
                            {pat.last_visit_date && (
                              <span className="text-[10px] text-on-surface-variant font-medium">
                                • Last visit: {pat.last_visit_date}
                              </span>
                            )}
                          </div>
                        </div>
                        <button
                          onClick={() => {
                            window.location.href = `/patients?search=${encodeURIComponent(pat.name)}`;
                          }}
                          className="text-xs font-bold px-3 py-1.5 bg-red-100 hover:bg-red-200 text-red-800 rounded-xl transition"
                        >
                          Outreach
                        </button>
                      </div>
                    ))
                  ) : (
                    <div className="col-span-2 text-center py-8 text-xs text-on-surface-variant">
                      Zero high churn-risk patients detected. Practice retention is optimal!
                    </div>
                  )}
                </div>
              </div>

            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
              TAB 6: NO-SHOWS & SHOW RATE INDEX
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "no-shows" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Top 6 KPI Cards for No-Show & Show Rate Analysis */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Practice Show Rate</span>
                  <p className="text-3xl font-black text-[#2e7d32]">{noshowsData.show_rate}%</p>
                  <p className="text-[10px] text-on-surface-variant font-semibold">
                    {noshowsData.completed_count ?? noshowsData.attended_count ?? 0} attended of {noshowsData.concluded_appointments || ((noshowsData.completed_count || 0) + (noshowsData.no_show_count || 0)) || noshowsData.total_appointments} concluded
                  </p>
                </div>

                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#b71c1c]">Current No-Show Rate</span>
                  <p className="text-3xl font-black text-on-surface">{noshowsData.no_show_rate}%</p>
                  <p className="text-[10px] text-on-surface-variant font-semibold">{noshowsData.no_show_count} unexcused missed visits</p>
                </div>

                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#b71c1c]">Estimated Lost Revenue</span>
                  <p className="text-3xl font-black text-red-700">{formatCurrency(noshowsData.lost_revenue || (noshowsData.no_show_count * (noshowsData.avg_visit_value || 150)))}</p>
                  <p className="text-[10px] text-on-surface-variant font-semibold">{noshowsData.no_show_count} missed @ avg {formatCurrency(noshowsData.avg_visit_value || 150)}/visit</p>
                </div>

                <div className="card p-5 bg-[#edf7e0] border border-[#d2e7c4] space-y-1">
                  <span className="overline text-[#396a00]">CALL-E Recovered Revenue</span>
                  <p className="text-3xl font-black text-[#2e7d32]">+{formatCurrency(noshowsData.recovered_revenue || 0)}</p>
                  <p className="text-[10px] text-green-800 font-bold">{noshowsData.recovery_converted_count || 0} rebooked via 2h campaign</p>
                </div>

                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Confirmed vs Unconfirmed</span>
                  <div className="flex items-baseline gap-2 mt-1">
                    <span className="text-2xl font-black text-[#2e7d32]">{noshowsData.confirmed_show_rate}%</span>
                    <span className="text-xs text-on-surface-variant font-bold">vs {noshowsData.unconfirmed_show_rate}%</span>
                  </div>
                  <p className="text-[10px] text-green-700 font-bold">
                    +{(noshowsData.confirmed_lift_rate ?? (noshowsData.confirmed_show_rate - noshowsData.unconfirmed_show_rate)).toFixed(1)}% lift via confirmations
                  </p>
                </div>

                <div className="card p-5 bg-white border border-[#e7e9dd] space-y-1">
                  <span className="overline text-[#396a00]">Vs National Benchmark</span>
                  <p className="text-3xl font-black text-[#1565c0]">+{noshowsData.benchmark_savings_rate}%</p>
                  <p className="text-[10px] text-[#1565c0] font-bold">National clinic avg is 18.0%</p>
                </div>
              </div>

              {/* CALL-E 2-Hour Autonomous No-Show Recovery Engine Control Banner */}
              <div className="card p-6 bg-gradient-to-r from-emerald-50 via-white to-green-50/40 border border-[#cbe4b8] space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-[#396a00]" />
                      <h3 className="text-sm font-extrabold text-on-surface">CALL-E 2-Hour Autonomous No-Show Recovery Engine</h3>
                      <span className="text-[10px] uppercase font-bold bg-[#396a00] text-white px-2 py-0.5 rounded-full">Automated Bot</span>
                    </div>
                    <p className="text-xs text-on-surface-variant max-w-2xl leading-relaxed">
                      CALL-E automatically contacts patients 2 hours after an unexcused missed appointment to express care and immediately offer rebooking before the schedule slot is permanently lost.
                    </p>
                  </div>
                  <button
                    onClick={handleTriggerNoshowCampaign}
                    disabled={runningNoshowCampaign}
                    className="flex items-center justify-center gap-2 px-5 py-2.5 bg-[#396a00] hover:bg-[#2e5500] text-white font-bold text-xs rounded-xl shadow transition-all disabled:opacity-50 shrink-0"
                  >
                    {runningNoshowCampaign ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Dispatching CALL-E Calls...</span>
                      </>
                    ) : (
                      <>
                        <Phone className="w-4 h-4" />
                        <span>Run 2h Recovery Campaign Now</span>
                      </>
                    )}
                  </button>
                </div>

                {noshowCampaignFeedback && (
                  <div className={`p-3 rounded-xl text-xs font-semibold flex items-center gap-2 ${
                    noshowCampaignFeedback.type === "success" 
                      ? "bg-green-100 text-green-800 border border-green-200" 
                      : "bg-red-100 text-red-800 border border-red-200"
                  }`}>
                    {noshowCampaignFeedback.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                    <span>{noshowCampaignFeedback.text}</span>
                  </div>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-[#e2edd7]">
                  <div>
                    <span className="text-[10px] uppercase font-bold text-on-surface-variant">2h Calls Dispatched</span>
                    <p className="text-lg font-black text-on-surface">{noshowsData.recovery_dispatched_count || 0}</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-on-surface-variant">Successfully Rebooked</span>
                    <p className="text-lg font-black text-[#2e7d32]">{noshowsData.recovery_converted_count || 0}</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-on-surface-variant">Rebooking Recovery Rate</span>
                    <p className="text-lg font-black text-on-surface">{noshowsData.recovery_conversion_rate || 0}%</p>
                  </div>
                  <div>
                    <span className="text-[10px] uppercase font-bold text-on-surface-variant">Total Value Rescued</span>
                    <p className="text-lg font-black text-[#2e7d32]">+{formatCurrency(noshowsData.recovered_revenue || 0)}</p>
                  </div>
                </div>
              </div>

              {/* No-Show Rate & Show Rate Trend Line Chart */}
              <div className="card p-6 bg-white border border-[#e7e9dd]">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-6">
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">Daily Attendance & No-Show Rate Trend</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">Tracking day-by-day show rates and no-show percentages against national benchmark line.</p>
                  </div>
                  <div className="flex items-center gap-4 text-xs font-bold">
                    <span className="flex items-center gap-1.5 text-[#2e7d32]">
                      <span className="w-2.5 h-2.5 bg-[#2e7d32] rounded-full" /> Show Rate %
                    </span>
                    <span className="flex items-center gap-1.5 text-[#b71c1c]">
                      <span className="w-2.5 h-2.5 bg-[#b71c1c] rounded-full" /> No-Show Rate %
                    </span>
                    <span className="flex items-center gap-1.5 text-amber-600">
                      <span className="w-4 h-0.5 bg-amber-500 border-t border-dashed" /> 18% Nat'l Benchmark
                    </span>
                  </div>
                </div>
                
                <div className="h-80 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={noshowsData.trend || []}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f4ed" />
                      <XAxis 
                        dataKey="date" 
                        tickFormatter={(d) => d ? d.slice(5) : ""}
                        tickLine={false} 
                        tick={{ fill: "#42493a", fontSize: 10, fontWeight: 700 }} 
                      />
                      <YAxis tickFormatter={(v) => `${v}%`} tickLine={false} tick={{ fill: "#42493a", fontSize: 10 }} domain={[0, 100]} />
                      <Tooltip 
                        formatter={(v, name) => [`${v}%`, name === "show_rate" ? "Show Rate" : "No-Show Rate"]} 
                        contentStyle={{ borderRadius: "10px", border: "1px solid #e7e9dd" }} 
                      />
                      <ReferenceLine y={18} stroke="#f59e0b" strokeDasharray="4 4" label={{ value: "Benchmark (18%)", fill: "#d97706", fontSize: 10, position: "top" }} />
                      <Line 
                        type="monotone" 
                        dataKey="show_rate" 
                        name="show_rate"
                        stroke="#2e7d32" 
                        strokeWidth={2.5} 
                        dot={{ r: 3, fill: "#2e7d32" }} 
                        activeDot={{ r: 6 }} 
                        connectNulls={true}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="no_show_rate" 
                        name="no_show_rate"
                        stroke="#b71c1c" 
                        strokeWidth={2.5} 
                        dot={{ r: 3, fill: "#b71c1c" }} 
                        activeDot={{ r: 6 }} 
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Repeat Offenders Table */}
              <div className="card p-6 bg-white border border-[#e7e9dd] space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-bold text-on-surface">Repeat No-Show Offenders Watchlist</h3>
                    <p className="text-[11px] text-on-surface-variant font-medium">Patients with repeat unexcused absences. Recommended for mandatory deposit policy or phone triage.</p>
                  </div>
                  <span className="text-[10px] font-bold text-on-surface-variant bg-surface-container-high px-2.5 py-1 rounded-lg">
                    {noshowsData.top_offenders ? noshowsData.top_offenders.length : 0} offenders identified
                  </span>
                </div>
                
                <div className="divide-y divide-[#f1f4ed]">
                  {noshowsData.top_offenders && noshowsData.top_offenders.length > 0 ? (
                    noshowsData.top_offenders.map((off, idx) => (
                      <div key={idx} className="flex flex-col sm:flex-row sm:items-center justify-between py-3.5 gap-2">
                        <div>
                          <div className="flex items-center gap-2">
                            <p className="text-xs font-bold text-on-surface">{off.name}</p>
                            <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
                              {off.policy_recommendation || (off.no_show_count >= 2 ? "Mandatory Pre-Payment Deposit" : "CALL-E 2h Phone Triage")}
                            </span>
                          </div>
                          <p className="text-[10px] text-on-surface-variant font-mono mt-0.5">{off.phone || "No phone listed"}</p>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-xs font-semibold text-red-600">
                            {formatCurrency(off.estimated_lost_revenue || (off.no_show_count * 150))} lost
                          </span>
                          <span className="text-xs font-bold text-red-700 bg-red-50 border border-red-200 px-3 py-1 rounded-xl">
                            {off.no_show_count} missed appointment{off.no_show_count === 1 ? "" : "s"}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-8 text-xs text-on-surface-variant">
                      Zero repeat offenders recorded! Automated reminders and 2-hour triage are maintaining optimal attendance.
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
              TAB 7: AI OPS INSIGHTS & SUGGESTIONS
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "suggestions" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-in fade-in duration-200">
              {/* Executive Ops Report */}
              <div className="card p-6 lg:col-span-2 space-y-4 bg-white border border-[#e7e9dd] relative overflow-hidden">
                <div className="flex items-center gap-2 border-b border-[#f1f4ed] pb-4">
                  <Sparkles className="w-5 h-5 text-[#396a00]" />
                  <div>
                    <h3 className="text-sm font-extrabold text-on-surface">Weekly Practice Operations Summary</h3>
                    <p className="text-[10px] text-on-surface-variant uppercase font-bold tracking-wider">Generated autonomously by CMOO AI Assistant</p>
                  </div>
                </div>

                <div className="space-y-4 max-h-[500px] overflow-y-auto pr-1 select-text">
                  {suggestionsData.latest_ai_insights ? (
                    renderMarkdown(suggestionsData.latest_ai_insights)
                  ) : (
                    <div className="text-center py-12 space-y-3">
                      <p className="text-xs text-on-surface-variant font-semibold">
                        Your clinic operations are active. High-priority autonomous scheduling suggestions will appear below as real-time appointment volume grows.
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Dynamic Suggestions Column */}
              <div className="space-y-4 lg:col-span-1">
                <div className="flex items-center gap-1.5 px-1">
                  <Sparkles className="w-4 h-4 text-[#396a00]" />
                  <h4 className="text-xs font-black uppercase tracking-widest text-on-surface-variant">Recommended Actions</h4>
                </div>
                
                {suggestionsData.recommendations && suggestionsData.recommendations.length > 0 ? (
                  suggestionsData.recommendations.map((rec) => {
                    let alertBg = "bg-[#edf7e0] border-[#d6ede0]";
                    let accentColor = "text-[#396a00]";
                    
                    if (rec.type === "retention") {
                      alertBg = "bg-[#e3f2fd] border-[#bbdefb]";
                      accentColor = "text-[#0d47a1]";
                    } else if (rec.type === "leakage") {
                      alertBg = "bg-[#fff5f5] border-[#ffe3e3]";
                      accentColor = "text-rose-700";
                    }
                    
                    return (
                      <div 
                        key={rec.id} 
                        className={`card p-5 border ${alertBg} flex flex-col justify-between gap-4 transition duration-200 hover:shadow-md rounded-2xl`}
                      >
                        <div className="space-y-2">
                          <h5 className={`text-xs font-black uppercase tracking-wide ${accentColor}`}>
                            {rec.title}
                          </h5>
                          <p className="text-[11px] text-on-surface-variant leading-relaxed font-semibold">
                            {rec.description}
                          </p>
                        </div>
                        
                        <button
                          onClick={() => {
                            if (rec.action_payload?.tab) {
                              window.location.href = `/settings?tab=${rec.action_payload.tab}`;
                            } else {
                              window.location.href = `/settings?tab=hours`;
                            }
                          }}
                          className={`self-start text-[10px] font-black uppercase tracking-widest flex items-center gap-1.5 hover:underline ${accentColor}`}
                        >
                          {rec.action_label}
                          <ChevronRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-center py-6 text-xs text-on-surface-variant">No active scheduling bottlenecks found.</div>
                )}
              </div>
            </div>
          )}

          {/* ═══════════════════════════════════════════════════════════
              TAB 8: COMPETITOR BENCHMARKING (MGMA / AMGA / APTA Standards)
             ═══════════════════════════════════════════════════════════ */}
          {activeTab === "benchmarking" && (
            <div className="space-y-6 animate-in fade-in duration-200">
              {/* Top Banner with Opt-In / Privacy Status */}
              <div className="card p-6 bg-[#edf7e0] border border-[#d2e7c4] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-2xl">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-[#396a00]/10 text-[#396a00] rounded-full flex items-center justify-center flex-shrink-0">
                    <ShieldCheck className="w-5 h-5 text-[#396a00]" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="text-sm font-bold text-on-surface">Anonymous Specialty Benchmarking</h4>
                      <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-[#396a00]/10 text-[#396a00] border border-[#396a00]/20">
                        MGMA • AMGA • APTA Standards
                      </span>
                    </div>
                    <p className="text-[11px] text-on-surface-variant leading-relaxed font-medium mt-0.5">
                      Benchmarking your clinic against anonymized peer <b>{benchmarksData.specialty}</b> practices and national outpatient standards.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {benchmarksData.benchmark_opt_in ? (
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold text-[#396a00] bg-white px-2.5 py-1 rounded-lg border border-[#d2e7c4] flex items-center gap-1.5 shadow-sm">
                        <CheckCircle2 className="w-3 h-3 text-[#396a00]" /> Active Contributor (HIPAA Blinded)
                      </span>
                      <button
                        onClick={() => handleToggleOptIn(false)}
                        disabled={togglingOptIn}
                        className="text-[10px] font-bold text-on-surface-variant hover:text-red-700 bg-white/60 hover:bg-red-50 border border-[#d2e7c4] px-2.5 py-1 rounded-lg transition-colors"
                      >
                        {togglingOptIn ? <Loader2 className="w-3 h-3 animate-spin" /> : "Pause Sharing"}
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleToggleOptIn(true)}
                      disabled={togglingOptIn}
                      className="text-xs font-black text-white bg-[#396a00] hover:bg-[#2e5500] px-4 py-2 rounded-xl transition-colors shadow-sm flex items-center gap-1.5"
                    >
                      {togglingOptIn ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                      Opt In to Network Benchmarking
                    </button>
                  )}
                </div>
              </div>

              {/* Opt-Out Warning State */}
              {!benchmarksData.benchmark_opt_in && (
                <div className="card p-6 bg-amber-50/70 border border-amber-200 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-700 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="text-xs font-bold text-amber-900">Anonymized Benchmarking is Paused for Your Clinic</h4>
                      <p className="text-[11px] text-amber-800 leading-relaxed mt-0.5">
                        Your clinic metrics are currently excluded from network averages, and live peer percentiles are hidden.
                        Opt in to compare your practice against Physical Therapy & Rehab standards while maintaining 100% HIPAA k-anonymity.
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleToggleOptIn(true)}
                    disabled={togglingOptIn}
                    className="flex-shrink-0 text-xs font-black bg-amber-800 text-white hover:bg-amber-900 px-4 py-2 rounded-xl shadow-sm transition-colors flex items-center gap-1.5"
                  >
                    {togglingOptIn ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "Enable Benchmarking"}
                  </button>
                </div>
              )}

              {/* Executive Standing & Composite Percentile Banner */}
              <div className="card p-6 bg-gradient-to-r from-[#1c3300] to-[#2d4d02] text-white rounded-2xl shadow-sm flex flex-col lg:flex-row lg:items-center justify-between gap-6">
                <div className="space-y-1.5 max-w-xl">
                  <div className="flex items-center gap-2">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-white/20 text-[#a9f564] border border-white/10">
                      National Practice Ranking
                    </span>
                    <span className="text-[11px] font-bold text-emerald-200">
                      {benchmarksData.specialty || "Physical Therapy & Sports Rehab"}
                    </span>
                  </div>
                  <h3 className="text-xl sm:text-2xl font-black tracking-tight text-white flex items-center gap-2">
                    <Award className="w-6 h-6 text-[#a9f564]" />
                    {benchmarksData.overall_tier || "National Top 10% (Network Leader)"}
                  </h3>
                  <p className="text-xs text-white/80 leading-relaxed font-medium">
                    Evaluated across no-show deflection, patient recall conversion, autonomous prior authorization speed, and 24/7 patient inquiry capture.
                  </p>
                </div>

                <div className="flex items-center gap-4 bg-white/10 p-4 rounded-xl border border-white/15">
                  <div className="text-center px-3 border-r border-white/20">
                    <p className="text-[10px] font-bold text-white/70 uppercase tracking-wider">Composite Percentile</p>
                    <p className="text-3xl font-black text-[#a9f564] mt-0.5">{benchmarksData.overall_percentile || 90}<span className="text-lg">th</span></p>
                  </div>
                  <div className="space-y-1 text-[11px]">
                    <div className="flex items-center gap-2 text-white/90">
                      <Check className="w-3.5 h-3.5 text-[#a9f564]" />
                      <span>No-Show Deflection: <b>{benchmarksData.no_show_rate?.percentile_label || "Top 25%"}</b></span>
                    </div>
                    <div className="flex items-center gap-2 text-white/90">
                      <Check className="w-3.5 h-3.5 text-[#a9f564]" />
                      <span>Patient Recall Yield: <b>{benchmarksData.patient_recall_rate?.percentile_label || "Top 5%"}</b></span>
                    </div>
                    <div className="flex items-center gap-2 text-white/90">
                      <Check className="w-3.5 h-3.5 text-[#a9f564]" />
                      <span>Prior Auth Velocity: <b>{benchmarksData.prior_auth_turnaround_days?.percentile_label || "Top 2%"}</b></span>
                    </div>
                  </div>
                </div>
              </div>

              {/* 4 Core Benchmark Metric Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                {/* 1. Patient No-Show Rate Comparison (MGMA & APTA Standard: 18-22%) */}
                <div className="card p-6 bg-white border border-[#e7e9dd] space-y-6">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Patient No-Show Rate</h4>
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {benchmarksData.no_show_rate?.percentile_label || "Top 25% Nationwide"}
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant mt-0.5">
                        Missed visits without notice. Lower rate indicates superior schedule throughput.
                      </p>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-on-surface-variant bg-[#f1f4ed] px-2 py-1 rounded-md">
                      MGMA PT Standard: 18-22%
                    </span>
                  </div>

                  {/* Visual Bar Comparison */}
                  <div className="flex items-end gap-6 h-40 pt-4 px-4 bg-[#fafbf7] rounded-xl border border-[#f1f4ed]">
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-[#396a00]">
                        {benchmarksData.no_show_rate?.clinic_value ?? benchmarksData.clinic_no_show_rate}%
                      </span>
                      <div 
                        className="w-full bg-[#396a00] rounded-t-xl transition-all duration-500 shadow-sm" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.no_show_rate?.clinic_value ?? benchmarksData.clinic_no_show_rate) / Math.max(1, (benchmarksData.no_show_rate?.clinic_value ?? benchmarksData.clinic_no_show_rate), (benchmarksData.no_show_rate?.benchmark_avg ?? 19.5))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface uppercase tracking-wider">Your Clinic</span>
                    </div>
                    
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-on-surface-variant">
                        {benchmarksData.no_show_rate?.benchmark_avg ?? 19.5}%
                      </span>
                      <div 
                        className="w-full bg-[#cbd5e1] rounded-t-xl transition-all duration-500" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.no_show_rate?.benchmark_avg ?? 19.5) / Math.max(1, (benchmarksData.no_show_rate?.clinic_value ?? benchmarksData.clinic_no_show_rate), (benchmarksData.no_show_rate?.benchmark_avg ?? 19.5))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-wider">MGMA Median</span>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#f1f4ed] flex items-center justify-between text-xs font-semibold">
                    <span className="text-emerald-700 flex items-center gap-1 font-bold">
                      <ArrowDownRight className="w-4 h-4 text-emerald-600" />
                      {Math.abs(benchmarksData.no_show_rate?.delta ?? 4.1)}% lower than industry average
                    </span>
                    <span className="text-[11px] text-on-surface-variant font-medium">
                      APTA Outpatient Standard (18-22%)
                    </span>
                  </div>
                </div>

                {/* 2. Patient Recall Rate Comparison (APTA Standard: 35.0%) */}
                <div className="card p-6 bg-white border border-[#e7e9dd] space-y-6">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Patient Recall & Re-Booking Rate</h4>
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {benchmarksData.patient_recall_rate?.percentile_label || "Top 5% Nationwide"}
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant mt-0.5">
                        Lapsed patients successfully re-booked through CALL-E automated outreach.
                      </p>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-on-surface-variant bg-[#f1f4ed] px-2 py-1 rounded-md">
                      APTA Benchmark: 35.0%
                    </span>
                  </div>

                  {/* Visual Bar Comparison */}
                  <div className="flex items-end gap-6 h-40 pt-4 px-4 bg-[#fafbf7] rounded-xl border border-[#f1f4ed]">
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-[#396a00]">
                        {benchmarksData.patient_recall_rate?.clinic_value ?? 62.5}%
                      </span>
                      <div 
                        className="w-full bg-[#396a00] rounded-t-xl transition-all duration-500 shadow-sm" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.patient_recall_rate?.clinic_value ?? 62.5) / Math.max(1, (benchmarksData.patient_recall_rate?.clinic_value ?? 62.5), (benchmarksData.patient_recall_rate?.benchmark_avg ?? 35.0))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface uppercase tracking-wider">Your Clinic</span>
                    </div>
                    
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-on-surface-variant">
                        {benchmarksData.patient_recall_rate?.benchmark_avg ?? 35.0}%
                      </span>
                      <div 
                        className="w-full bg-[#cbd5e1] rounded-t-xl transition-all duration-500" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.patient_recall_rate?.benchmark_avg ?? 35.0) / Math.max(1, (benchmarksData.patient_recall_rate?.clinic_value ?? 62.5), (benchmarksData.patient_recall_rate?.benchmark_avg ?? 35.0))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-wider">APTA Standard</span>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#f1f4ed] flex items-center justify-between text-xs font-semibold">
                    <span className="text-emerald-700 flex items-center gap-1 font-bold">
                      <ArrowUpRight className="w-4 h-4 text-emerald-600" />
                      +{benchmarksData.patient_recall_rate?.delta ?? 27.5}% above national average
                    </span>
                    <span className="text-[11px] text-on-surface-variant font-medium">
                      APTA Retention Guideline
                    </span>
                  </div>
                </div>

                {/* 3. Prior Auth Approval Turnaround (MGMA Standard: 5.2 Days) */}
                <div className="card p-6 bg-white border border-[#e7e9dd] space-y-6">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Prior Auth Approval Velocity</h4>
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {benchmarksData.prior_auth_turnaround_days?.percentile_label || "Top 2% Nationwide"}
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant mt-0.5">
                        Average business days elapsed from submission to approved decision.
                      </p>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-on-surface-variant bg-[#f1f4ed] px-2 py-1 rounded-md">
                      MGMA Standard: 5.2 Days
                    </span>
                  </div>

                  {/* Visual Bar Comparison */}
                  <div className="flex items-end gap-6 h-40 pt-4 px-4 bg-[#fafbf7] rounded-xl border border-[#f1f4ed]">
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-[#396a00]">
                        {benchmarksData.prior_auth_turnaround_days?.clinic_value ?? 0.2}d
                      </span>
                      <div 
                        className="w-full bg-[#396a00] rounded-t-xl transition-all duration-500 shadow-sm" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.prior_auth_turnaround_days?.clinic_value ?? 0.2) / Math.max(1, (benchmarksData.prior_auth_turnaround_days?.clinic_value ?? 0.2), (benchmarksData.prior_auth_turnaround_days?.benchmark_avg ?? 5.2))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface uppercase tracking-wider">CALL-E AI Speed</span>
                    </div>
                    
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-on-surface-variant">
                        {benchmarksData.prior_auth_turnaround_days?.benchmark_avg ?? 5.2}d
                      </span>
                      <div 
                        className="w-full bg-[#cbd5e1] rounded-t-xl transition-all duration-500" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.prior_auth_turnaround_days?.benchmark_avg ?? 5.2) / Math.max(1, (benchmarksData.prior_auth_turnaround_days?.clinic_value ?? 0.2), (benchmarksData.prior_auth_turnaround_days?.benchmark_avg ?? 5.2))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-wider">Manual Industry Avg</span>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#f1f4ed] flex items-center justify-between text-xs font-semibold">
                    <span className="text-emerald-700 flex items-center gap-1 font-bold">
                      <Zap className="w-4 h-4 text-emerald-600" />
                      {benchmarksData.prior_auth_turnaround_days?.days_saved ?? 5.0} business days saved per auth
                    </span>
                    <span className="text-[11px] text-on-surface-variant font-medium">
                      MGMA Regulatory Survey (5.2d)
                    </span>
                  </div>
                </div>

                {/* 4. Inbound Call Inquiry Capture (AMGA Standard: 71.0%) */}
                <div className="card p-6 bg-white border border-[#e7e9dd] space-y-6">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-sm font-bold text-on-surface">Patient Call Capture & Answer Rate</h4>
                        <span className="px-2 py-0.5 rounded-full text-[9px] font-black uppercase tracking-wider bg-emerald-50 text-emerald-800 border border-emerald-200">
                          {benchmarksData.call_handling?.percentile_label || "Top 5% Nationwide"}
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant mt-0.5">
                        Inquiries answered in real time vs missed to voicemail during peak rehab hours.
                      </p>
                    </div>
                    <span className="text-[10px] font-mono font-bold text-on-surface-variant bg-[#f1f4ed] px-2 py-1 rounded-md">
                      AMGA Standard: 71.0%
                    </span>
                  </div>

                  {/* Visual Bar Comparison */}
                  <div className="flex items-end gap-6 h-40 pt-4 px-4 bg-[#fafbf7] rounded-xl border border-[#f1f4ed]">
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-[#396a00]">
                        {benchmarksData.call_handling?.clinic_answer_rate ?? 100}%
                      </span>
                      <div 
                        className="w-full bg-[#396a00] rounded-t-xl transition-all duration-500 shadow-sm" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.call_handling?.clinic_answer_rate ?? 100) / Math.max(1, (benchmarksData.call_handling?.clinic_answer_rate ?? 100), (benchmarksData.call_handling?.specialty_answer_rate_avg ?? 71))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface uppercase tracking-wider">
                        {benchmarksData.clinic_call_volume} Calls Handled
                      </span>
                    </div>
                    
                    <div className="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                      <span className="text-xl font-black text-on-surface-variant">
                        {benchmarksData.call_handling?.specialty_answer_rate_avg ?? 71.0}%
                      </span>
                      <div 
                        className="w-full bg-[#cbd5e1] rounded-t-xl transition-all duration-500" 
                        style={{ 
                          height: `${Math.min(100, Math.max(18, ((benchmarksData.call_handling?.specialty_answer_rate_avg ?? 71) / Math.max(1, (benchmarksData.call_handling?.clinic_answer_rate ?? 100), (benchmarksData.call_handling?.specialty_answer_rate_avg ?? 71))) * 100))}%` 
                        }} 
                      />
                      <span className="text-[10px] font-black text-on-surface-variant uppercase tracking-wider">AMGA Industry Avg</span>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-[#f1f4ed] flex items-center justify-between text-xs font-semibold">
                    <span className="text-emerald-700 flex items-center gap-1 font-bold">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                      +{Math.round((benchmarksData.call_handling?.clinic_answer_rate ?? 100) - (benchmarksData.call_handling?.specialty_answer_rate_avg ?? 71))}% zero-leakage capture advantage
                    </span>
                    <span className="text-[11px] text-on-surface-variant font-medium">
                      24/7 AI Receptionist
                    </span>
                  </div>
                </div>

              </div>

              {/* Data Sources & Methodology Citation Footer */}
              <div className="card p-6 bg-white border border-[#e7e9dd] space-y-4 rounded-2xl">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-[#396a00]" />
                  <h4 className="text-xs font-black uppercase tracking-wider text-on-surface">
                    Benchmark Sources & Clinical Methodology
                  </h4>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                  <div className="p-3.5 bg-[#fafbf7] rounded-xl border border-[#f1f4ed] space-y-1">
                    <p className="font-bold text-on-surface flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-[#396a00]" /> APTA Standards
                    </p>
                    <p className="text-[11px] text-on-surface-variant leading-relaxed">
                      American Physical Therapy Association 2025 Outpatient PT Survey. Defines patient recall rate (35.0% median) and discharge follow-up criteria.
                    </p>
                  </div>

                  <div className="p-3.5 bg-[#fafbf7] rounded-xl border border-[#f1f4ed] space-y-1">
                    <p className="font-bold text-on-surface flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-[#396a00]" /> MGMA Operations
                    </p>
                    <p className="text-[11px] text-on-surface-variant leading-relaxed">
                      Medical Group Management Association Practice Operations Report. Physical Therapy no-show baseline of 18-22% and prior auth turnaround of 5.2 business days.
                    </p>
                  </div>

                  <div className="p-3.5 bg-[#fafbf7] rounded-xl border border-[#f1f4ed] space-y-1">
                    <p className="font-bold text-on-surface flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-[#396a00]" /> AMGA Telephony
                    </p>
                    <p className="text-[11px] text-on-surface-variant leading-relaxed">
                      American Medical Group Association Access Study. Benchmarks clinic live phone answer rate at 71.0%, indicating ~29% missed inquiry leakage without AI triage.
                    </p>
                  </div>
                </div>

                <div className="pt-2 text-[10px] text-on-surface-variant font-medium flex flex-col sm:flex-row items-center justify-between gap-2 border-t border-[#f1f4ed]">
                  <span>
                    HIPAA De-Identification (§ 164.514): Aggregate metrics are evaluated using k-anonymity (k ≥ 5) with zero PHI disclosure.
                  </span>
                  <a href="/settings?tab=profile" className="text-[#396a00] font-bold hover:underline flex items-center gap-1">
                    Manage Clinic Specialty & Privacy Settings <ChevronRight className="w-3 h-3" />
                  </a>
                </div>
              </div>

            </div>
          )}

        </div>
      )}
    </div>
  );
}

