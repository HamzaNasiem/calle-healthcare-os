import React, { useState, useEffect, useCallback } from 'react';
import {
  PhoneCall,
  PhoneForwarded,
  PhoneOutgoing,
  CalendarCheck,
  UserX,
  RotateCcw,
  Star,
  Play,
  RefreshCw,
  CheckCircle2,
  AlertCircle,
  Clock,
  ShieldCheck,
  Sparkles,
  Search,
  Filter,
  Eye,
  X,
  Zap,
  Users,
  Target,
  ChevronRight,
  Copy,
  Check,
  Activity,
  DollarSign,
  Layers,
  Send,
  Radio,
  FileText,
  Sliders,
  Volume2,
  Bot,
  ListChecks,
  ArrowRight,
  TrendingUp,
  Sparkle
} from 'lucide-react';
import api from '../lib/api';
import { useAuth } from '../context/AuthContext';

const OutboundCampaigns = () => {
  const { clinicId } = useAuth();

  // ── Core Data State ──────────────────────────────────────────────────────────
  const [statusInfo, setStatusInfo] = useState(null);
  const [estimates, setEstimates] = useState(null);
  const [calls, setCalls] = useState([]);
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // ── View & Filter State ──────────────────────────────────────────────────────
  const [activeMainTab, setActiveMainTab] = useState('campaigns'); // 'campaigns' | 'goals' | 'feed'
  const [feedFilter, setFeedFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [triggering, setTriggering] = useState({});
  const [triggeringAll, setTriggeringAll] = useState(false);
  const [notification, setNotification] = useState(null);

  // ── Campaign Parameter Customizations ────────────────────────────────────────
  const [recallDays, setRecallDays] = useState(30);
  const [waitlistDate, setWaitlistDate] = useState('Tomorrow');
  const [waitlistTime, setWaitlistTime] = useState('10:30 AM');

  // ── Single Live Test Call Modal State ─────────────────────────────────────────
  const [showSingleModal, setShowSingleModal] = useState(false);
  const [appointmentsList, setAppointmentsList] = useState([]);
  const [singleSource, setSingleSource] = useState('existing'); // 'existing' | 'custom'
  const [singleAppointmentId, setSingleAppointmentId] = useState('');
  const [singlePatientId, setSinglePatientId] = useState('');
  const [singlePatientName, setSinglePatientName] = useState('');
  const [singleCampaign, setSingleCampaign] = useState('confirmation');
  const [singlePhone, setSinglePhone] = useState('');
  const [singleClinicName, setSingleClinicName] = useState('');
  const [singleTime, setSingleTime] = useState('');
  const [singleRecallType, setSingleRecallType] = useState('Annual Routine Check-up');
  const [singleRecallDays, setSingleRecallDays] = useState(30);
  const [singleSlotDate, setSingleSlotDate] = useState('Tomorrow');
  const [singleSlotTime, setSingleSlotTime] = useState('10:30 AM');
  const [singleWaitForResult, setSingleWaitForResult] = useState(false); // Non-blocking dispatch for instant 1s phone ringing
  const [singleEngine, setSingleEngine] = useState('instant'); // 'instant' (1s SIP ring) | 'calle' (autonomous task)
  const [singleSubmitting, setSingleSubmitting] = useState(false);
  const [singleStep, setSingleStep] = useState(1);
  const [singleResult, setSingleResult] = useState(null);
  const [singleCopied, setSingleCopied] = useState(false);

  // ── Published Goal Run Modal State (CALL-E 0.6.0) ────────────────────────────
  const [showGoalModal, setShowGoalModal] = useState(false);
  const [selectedGoal, setSelectedGoal] = useState(null);
  const [goalPhone, setGoalPhone] = useState('');
  const [goalVariables, setGoalVariables] = useState({});
  const [goalWaitForResult, setGoalWaitForResult] = useState(true);
  const [goalSubmitting, setGoalSubmitting] = useState(false);
  const [goalResult, setGoalResult] = useState(null);

  // ── Call Detail Inspector Modal State ─────────────────────────────────────────
  const [selectedCall, setSelectedCall] = useState(null);
  const [callEvents, setCallEvents] = useState([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [inspectorCopied, setInspectorCopied] = useState(false);

  // ── Toast Notification Helper ────────────────────────────────────────────────
  const notify = (msg, type = 'success') => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 5000);
  };

  // ── Fetch All Data ───────────────────────────────────────────────────────────
  const fetchData = useCallback(async (isManualRefresh = false) => {
    if (isManualRefresh) setRefreshing(true);
    try {
      // 1. CALL-E Status
      const statusRes = await api.get('/calle/status').catch(() => null);
      if (statusRes && statusRes.data) {
        setStatusInfo(statusRes.data);
      } else {
        setStatusInfo({ configured: false, live_mode: false, mode: 'offline', api_version: '0.6.0' });
      }

      // 2. Campaign Estimates & Backlog Counts
      const estRes = await api.get('/calle/campaigns/estimates').catch(() => null);
      if (estRes && estRes.data) {
        setEstimates(estRes.data);
      } else {
        setEstimates({
          total_queued: 0,
          cost_per_call: 0.07,
          estimated_total_cost: 0.0,
          campaigns: {
            confirmation: { queue_count: 0, estimated_cost: 0.0 },
            no_show: { queue_count: 0, estimated_cost: 0.0 },
            recall: { queue_count: 0, estimated_cost: 0.0 },
            survey: { queue_count: 0, estimated_cost: 0.0 },
            waitlist: { queue_count: 0, estimated_cost: 0.0 },
          },
          counts: { confirmation: 0, no_show: 0, recall_30: 0, recall_60: 0, recall_90: 0, survey: 0, waitlist: 0 }
        });
      }


      // 3. Outbound Calls Feed
      const callsRes = await api.get('/calle/calls?limit=100').catch(() => null);
      if (callsRes && callsRes.data && callsRes.data.data) {
        setCalls(callsRes.data.data);
      } else {
        setCalls([]);
      }

      // 4. Published Goals (CALL-E API 0.6.0)
      const goalsRes = await api.get('/calle/goals').catch(() => null);
      if (goalsRes && goalsRes.data && goalsRes.data.data) {
        setGoals(goalsRes.data.data);
      } else {
        setGoals([]);
      }

      // 5. Scheduled Appointments for Single Test Call Linking
      const apptRes = await api.get('/appointments?limit=100').catch(() => null);
      if (apptRes && apptRes.data && apptRes.data.data) {
        setAppointmentsList(apptRes.data.data);
      }
    } catch (err) {
      console.error('Error fetching CALL-E data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(false), 12000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ── Fetch Call Events for Inspector ──────────────────────────────────────────
  const handleInspectCall = async (call) => {
    setSelectedCall(call);
    setCallEvents([]);
    if (call.calle_call_id) {
      setLoadingEvents(true);
      try {
        const evRes = await api.get(`/calle/calls/${call.calle_call_id}/events`).catch(() => null);
        if (evRes && evRes.data && evRes.data.data) {
          setCallEvents(evRes.data.data);
        }
      } catch (e) {
        console.warn('Events fetch error:', e);
      } finally {
        setLoadingEvents(false);
      }
    }
  };

  // ── Open Test Single Modal Prefilled for Specific Campaign ────────────────────
  const handleOpenTestModal = (campaignType = 'confirmation') => {
    setSingleCampaign(campaignType);
    setSingleResult(null);
    setSingleStep(1);
    setShowSingleModal(true);
  };

  // ── Trigger Batch Campaign ───────────────────────────────────────────────────
  const handleTriggerCampaign = async (type) => {
    setTriggering(prev => ({ ...prev, [type]: true }));
    try {
      let endpoint = `/calle/campaigns/${type}`;
      let body = {};
      if (type === 'recall') {
        body = { days_threshold: recallDays, limit: 20 };
      } else if (type === 'waitlist') {
        body = { slot_date: waitlistDate, slot_time: waitlistTime, limit: 15 };
      }

      const res = await api.post(endpoint, body);
      notify(res.data?.message || `Campaign '${type}' batch dispatched successfully!`);
      fetchData(false);
    } catch (err) {
      notify(err.response?.data?.detail || `Failed to dispatch ${type} campaign`, 'error');
    } finally {
      setTriggering(prev => ({ ...prev, [type]: false }));
    }
  };

  // ── Trigger All Active Campaigns Master Batch ─────────────────────────────────
  const handleTriggerAllCampaigns = async () => {
    if (!window.confirm('Are you sure you want to dispatch all active automated outbound campaigns now?')) return;
    setTriggeringAll(true);
    try {
      await Promise.allSettled([
        api.post('/calle/campaigns/confirmation', {}),
        api.post('/calle/campaigns/no-show', {}),
        api.post('/calle/campaigns/recall', { days_threshold: recallDays, limit: 20 }),
        api.post('/calle/campaigns/survey', {}),
        api.post('/calle/campaigns/waitlist', { slot_date: waitlistDate, slot_time: waitlistTime, limit: 15 }),
      ]);
      notify('All automated campaign batches dispatched successfully!');
      fetchData(false);
    } catch (err) {
      notify('Batch dispatch completed with some warnings. Check activity log.', 'info');
    } finally {
      setTriggeringAll(false);
    }
  };

  // ── Appointment Selector Handler for Single Call ─────────────────────────────
  const handleSelectAppt = (apptId) => {
    setSingleAppointmentId(apptId);
    if (!apptId) {
      setSinglePhone('');
      setSinglePatientId('');
      setSinglePatientName('');
      setSingleTime('');
      return;
    }
    const appt = appointmentsList.find(a => String(a.id) === String(apptId));
    if (appt) {
      setSinglePhone(appt.patient_phone || '');
      setSinglePatientId(appt.patient_id || '');
      setSinglePatientName(appt.patient_name || '');
      if (appt.datetime) {
        try {
          const d = new Date(appt.datetime);
          setSingleTime(d.toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true }));
        } catch (e) {
          setSingleTime(appt.datetime);
        }
      }
    }
  };

  // ── Single Live Test Call Submission ─────────────────────────────────────────
  const handleSingleCallSubmit = async (e) => {
    e.preventDefault();
    if (!singlePhone) {
      notify('Please enter a recipient phone number', 'error');
      return;
    }

    setSingleSubmitting(true);
    setSingleResult(null);

    // Simulate progress animation steps
    const stepTimer1 = setTimeout(() => setSingleStep(2), 800);
    const stepTimer2 = setTimeout(() => setSingleStep(3), 2200);

    try {
      const payload = {
        phone: singlePhone,
        campaign_type: singleCampaign,
        appointment_id: singleAppointmentId || undefined,
        patient_id: singlePatientId || undefined,
        patient_name: singlePatientName || undefined,
        clinic_name: singleClinicName || undefined,
        time_str: singleCampaign === 'no_show' ? 'today at 10:00 AM' : (singleTime || undefined),
        days_since_last_visit: singleRecallDays,
        recall_type: singleRecallType,
        slot_date: singleSlotDate,
        slot_time: singleSlotTime,
        wait_for_completion: singleWaitForResult,
        engine: singleEngine,
      };

      const res = await api.post('/calle/calls/single', payload);
      setSingleResult(res.data);
      notify(`Test call executed! Status: ${res.data?.status || 'completed'}`);
      fetchData(false);
    } catch (err) {
      notify(err.response?.data?.detail || 'Failed to execute test call', 'error');
    } finally {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      setSingleSubmitting(false);
      setSingleStep(1);
    }
  };

  // ── Goal Run Submission (CALL-E 0.6.0) ────────────────────────────────────────
  const handleOpenGoalModal = (goal) => {
    setSelectedGoal(goal);
    setGoalPhone('');
    setGoalResult(null);
    const initialVars = {};
    if (goal.variables) {
      Object.keys(goal.variables).forEach(k => {
        initialVars[k] = '';
      });
    }
    setGoalVariables(initialVars);
    setShowGoalModal(true);
  };

  const handleGoalRunSubmit = async (e) => {
    e.preventDefault();
    if (!selectedGoal || !goalPhone) return;

    setGoalSubmitting(true);
    setGoalResult(null);
    try {
      const res = await api.post(`/calle/goals/${selectedGoal.id}/runs`, {
        phone: goalPhone,
        variables: goalVariables,
        wait_for_completion: goalWaitForResult,
      });
      setGoalResult(res.data);
      notify(`Goal run '${selectedGoal.name}' triggered successfully!`);
      fetchData(false);
    } catch (err) {
      notify(err.response?.data?.detail || 'Failed to trigger goal run', 'error');
    } finally {
      setGoalSubmitting(false);
    }
  };

  // ── Filtered Outbound Calls Feed ─────────────────────────────────────────────
  const filteredCalls = calls.filter(c => {
    if (feedFilter !== 'all' && c.campaign_type !== feedFilter) return false;
    if (statusFilter !== 'all' && c.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = String(c.calle_call_id || '').toLowerCase().includes(q);
      const matchSummary = String(c.summary || '').toLowerCase().includes(q);
      const matchType = String(c.campaign_type || '').toLowerCase().includes(q);
      const matchResult = JSON.stringify(c.structured_result || {}).toLowerCase().includes(q);
      if (!matchId && !matchSummary && !matchType && !matchResult) return false;
    }
    return true;
  });

  // ── Aggregate Metrics ────────────────────────────────────────────────────────
  const totalCallsCount = calls.length;
  const completedCallsCount = calls.filter(c => c.status === 'completed').length;
  const confirmedApptsCount = calls.filter(
    c => c.structured_result?.will_attend === 'yes' || c.structured_result?.appointment_status === 'confirmed'
  ).length;
  const rescheduledCount = calls.filter(
    c => c.structured_result?.will_attend === 'rescheduled' || c.structured_result?.response_type === 'rescheduled'
  ).length;

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-300">
      {/* ── Toast Notification ─────────────────────────────────────────────── */}
      {notification && (
        <div
          className={`fixed top-5 right-5 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-2xl border text-sm font-medium transition-all transform animate-in slide-in-from-top-2 ${
            notification.type === 'error'
              ? 'bg-red-950/90 border-red-500/50 text-red-200 shadow-red-900/20'
              : 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200 shadow-emerald-900/20'
          }`}
        >
          {notification.type === 'error' ? (
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 flex-shrink-0" />
          )}
          <span>{notification.msg}</span>
        </div>
      )}

      {/* ── Header Hero Banner ─────────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl border border-emerald-500/20 bg-gradient-to-r from-emerald-950/50 via-surface to-surface p-6 sm:p-8">
        <div className="absolute top-0 right-0 -mt-12 -mr-12 w-80 h-80 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-1/3 -mb-12 w-64 h-64 bg-teal-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2.5 max-w-3xl">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                <Sparkles className="w-3.5 h-3.5" />
                CALL-E Voice AI Active (v{statusInfo?.api_version || '0.6.0'})
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-surface-variant text-on-surface-variant border border-outline/10">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                HIPAA Certified Scrubber
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
                5 Automated Workflows
              </span>
            </div>

            <h1 className="page-header-title text-2xl sm:text-3xl font-extrabold tracking-tight">
              CALL-E Autonomous Outbound Campaigns
            </h1>
            <p className="text-sm text-on-surface-variant leading-relaxed">
              Fully autonomous, HIPAA-compliant patient outreach for appointment confirmations, no-show recoveries, routine recalls, satisfaction surveys, and instant waitlist backfills.
            </p>
          </div>

          <div className="flex items-center gap-3 flex-shrink-0 flex-wrap">
            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="p-2.5 rounded-xl border border-outline/20 hover:bg-surface-variant text-on-surface-variant transition-all disabled:opacity-50"
              title="Refresh Engine Feed"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
            </button>

            <button
              onClick={() => handleOpenTestModal('confirmation')}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-[#1a3a2e] transition-all shadow-lg hover:opacity-95 active:scale-95 border border-emerald-400/30"
              style={{ backgroundColor: '#7FCD4D' }}
            >
              <PhoneForwarded className="w-4 h-4" />
              <span>Live Test Call</span>
            </button>
          </div>
        </div>

        {/* ── Key Performance Metrics Grid ─────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3.5 mt-6 pt-6 border-t border-outline/10">
          <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/5">
            <div className="flex items-center justify-between text-on-surface-variant text-xs font-semibold">
              <span>Total Outbound Calls</span>
              <PhoneCall className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <p className="text-xl sm:text-2xl font-bold text-on-surface mt-1">{totalCallsCount}</p>
          </div>

          <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/5">
            <div className="flex items-center justify-between text-on-surface-variant text-xs font-semibold">
              <span>Completed Calls</span>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            </div>
            <p className="text-xl sm:text-2xl font-bold text-emerald-400 mt-1">{completedCallsCount}</p>
          </div>

          <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/5">
            <div className="flex items-center justify-between text-on-surface-variant text-xs font-semibold">
              <span>Confirmed Attendance</span>
              <CalendarCheck className="w-3.5 h-3.5 text-sky-400" />
            </div>
            <p className="text-xl sm:text-2xl font-bold text-sky-400 mt-1">{confirmedApptsCount}</p>
          </div>

          <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/5">
            <div className="flex items-center justify-between text-on-surface-variant text-xs font-semibold">
              <span>Rescheduled Recoveries</span>
              <RotateCcw className="w-3.5 h-3.5 text-amber-400" />
            </div>
            <p className="text-xl sm:text-2xl font-bold text-amber-400 mt-1">{rescheduledCount}</p>
          </div>

          <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/5 col-span-2 sm:col-span-1">
            <div className="flex items-center justify-between text-on-surface-variant text-xs font-semibold">
              <span>Engine Status</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
            </div>
            <p className="text-sm font-bold text-emerald-400 mt-1 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              {statusInfo?.live_mode ? 'Live CALL-E API' : 'Dry-Run Mode'}
            </p>
          </div>
        </div>
      </div>

      {/* ── Main Navigation Sub-Bar ─────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-outline/10 pb-4">
        <div className="tab-group">
          <button
            onClick={() => setActiveMainTab('campaigns')}
            className={`tab-item flex items-center gap-2 ${activeMainTab === 'campaigns' ? 'active' : ''}`}
          >
            <Layers className="w-4 h-4" />
            <span>5 Automated Campaigns</span>
          </button>

          <button
            onClick={() => setActiveMainTab('goals')}
            className={`tab-item flex items-center gap-2 ${activeMainTab === 'goals' ? 'active' : ''}`}
          >
            <Target className="w-4 h-4" />
            <span>Published Goals (API 0.6.0)</span>
            {goals.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-400">
                {goals.length}
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveMainTab('feed')}
            className={`tab-item flex items-center gap-2 ${activeMainTab === 'feed' ? 'active' : ''}`}
          >
            <Activity className="w-4 h-4" />
            <span>Live Activity Feed</span>
            {calls.length > 0 && (
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-surface-variant text-on-surface-variant">
                {calls.length}
              </span>
            )}
          </button>
        </div>

        {/* ── Master Batch Dispatcher Bar ──────────────────────────────────── */}
        {activeMainTab === 'campaigns' && (
          <div className="flex items-center gap-3 bg-surface-variant/40 p-1.5 px-3 rounded-xl border border-outline/10 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-on-surface-variant">Backlog Queue:</span>
              <span className="font-bold text-emerald-400 px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
                {estimates?.total_queued || 0} calls ready
              </span>
              <span className="text-on-surface-variant/60">|</span>
              <span className="text-on-surface-variant">Est. Cost:</span>
              <span className="font-bold text-on-surface">
                ${estimates?.estimated_total_cost?.toFixed(2) || '0.00'}
              </span>
            </div>

            <button
              onClick={handleTriggerAllCampaigns}
              disabled={triggeringAll || (estimates?.total_queued === 0)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold text-white transition-all shadow hover:opacity-95 active:scale-95 disabled:opacity-40"
              style={{ background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)' }}
            >
              <Play className={`w-3.5 h-3.5 fill-current ${triggeringAll ? 'animate-spin' : ''}`} />
              <span>{triggeringAll ? 'Dispatching...' : 'Dispatch All Due'}</span>
            </button>
          </div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* TAB 1: 5 AUTOMATED CAMPAIGN CARDS                                     */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {activeMainTab === 'campaigns' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {/* ── CARD 1: 24-Hour Appointment Confirmation ─────────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-emerald-500/40 transition-all border border-outline/10 group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-emerald-500/15 text-emerald-400 flex items-center justify-center border border-emerald-500/25 group-hover:scale-110 transition-transform">
                    <CalendarCheck className="w-5 h-5" />
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    24h Prior
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-on-surface text-base">24-Hour Appointment Confirmation</h3>
                  <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                    Calls patients 24 hours prior to scheduled visits to confirm attendance, answer prep questions, or handle reschedule requests.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-surface-variant/40 border border-outline/5 flex items-center justify-between text-xs">
                  <span className="text-on-surface-variant">Tomorrow's Queue:</span>
                  <span className="font-bold text-emerald-400">
                    {estimates?.campaigns?.confirmation?.queue_count || 0} patients ready (~${estimates?.campaigns?.confirmation?.estimated_cost?.toFixed(2) || '0.28'})
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-outline/10 space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('confirmation')}
                    disabled={triggering['confirmation']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-400 text-xs font-bold border border-emerald-500/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['confirmation'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['confirmation'] ? 'Dispatching...' : 'Run Confirmation Batch'}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('confirmation')}
                    className="p-2.5 rounded-xl border border-outline/20 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 2: 2-Hour Post-No-Show Recovery ─────────────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-amber-500/40 transition-all border border-outline/10 group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/15 text-amber-400 flex items-center justify-center border border-amber-500/25 group-hover:scale-110 transition-transform">
                    <UserX className="w-5 h-5" />
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    2h Post-Miss
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-on-surface text-base">2-Hour Post-No-Show Recovery</h3>
                  <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                    Calls patients within 2 hours of a missed appointment to express care, address barriers, and re-book their visit immediately.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-surface-variant/40 border border-outline/5 flex items-center justify-between text-xs">
                  <span className="text-on-surface-variant">Today's Missed:</span>
                  <span className="font-bold text-amber-400">
                    {estimates?.campaigns?.no_show?.queue_count || 0} no-shows ready (~${estimates?.campaigns?.no_show?.estimated_cost?.toFixed(2) || '0.14'})
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-outline/10 space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('no-show')}
                    disabled={triggering['no-show']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 text-xs font-bold border border-amber-500/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['no-show'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['no-show'] ? 'Dispatching...' : 'Run Recovery Batch'}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('no_show')}
                    className="p-2.5 rounded-xl border border-outline/20 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 3: 30/60/90-Day Patient Recall ──────────────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-sky-500/40 transition-all border border-outline/10 group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-sky-500/15 text-sky-400 flex items-center justify-center border border-sky-500/25 group-hover:scale-110 transition-transform">
                    <RotateCcw className="w-5 h-5" />
                  </div>
                  <div className="flex items-center bg-surface-variant rounded-lg p-0.5 border border-outline/10 text-xs">
                    {[30, 60, 90].map(d => (
                      <button
                        key={d}
                        onClick={() => setRecallDays(d)}
                        className={`px-2 py-0.5 rounded-md font-bold text-[10px] transition-all ${
                          recallDays === d ? 'bg-sky-500 text-slate-950' : 'text-on-surface-variant hover:text-on-surface'
                        }`}
                      >
                        {d}d
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="font-bold text-on-surface text-base">30/60/90-Day Patient Recall</h3>
                  <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                    Re-engages overdue patients due for follow-ups, preventive screenings, chronic care check-ups, and annual wellness visits.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-surface-variant/40 border border-outline/5 flex items-center justify-between text-xs">
                  <span className="text-on-surface-variant">{recallDays}-Day Backlog:</span>
                  <span className="font-bold text-sky-400">
                    {estimates?.counts?.[`recall_${recallDays}`] || estimates?.campaigns?.recall?.queue_count || 0} patients ready
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-outline/10 space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('recall')}
                    disabled={triggering['recall']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-sky-500/15 hover:bg-sky-500/25 text-sky-400 text-xs font-bold border border-sky-500/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['recall'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['recall'] ? 'Dispatching...' : `Run ${recallDays}d Recall Batch`}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('recall')}
                    className="p-2.5 rounded-xl border border-outline/20 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 4: Post-Visit Satisfaction Survey (NPS) ─────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-purple-500/40 transition-all border border-outline/10 group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-purple-500/15 text-purple-400 flex items-center justify-center border border-purple-500/25 group-hover:scale-110 transition-transform">
                    <Star className="w-5 h-5" />
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                    Post-Visit NPS
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-on-surface text-base">Post-Visit Satisfaction Survey</h3>
                  <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                    Collects 1-10 Net Promoter Scores (NPS) and structured quality feedback within hours of completed clinical visits.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-surface-variant/40 border border-outline/5 flex items-center justify-between text-xs">
                  <span className="text-on-surface-variant">Today's Completed:</span>
                  <span className="font-bold text-purple-400">
                    {estimates?.campaigns?.survey?.queue_count || 0} visits ready (~${estimates?.campaigns?.survey?.estimated_cost?.toFixed(2) || '0.14'})
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-outline/10 space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('survey')}
                    disabled={triggering['survey']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-purple-500/15 hover:bg-purple-500/25 text-purple-400 text-xs font-bold border border-purple-500/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['survey'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['survey'] ? 'Dispatching...' : 'Run Survey Batch'}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('survey')}
                    className="p-2.5 rounded-xl border border-outline/20 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 5: Instant Waitlist Backfill ────────────────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-teal-500/40 transition-all border border-outline/10 group relative overflow-hidden md:col-span-2 lg:col-span-2">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-teal-500/15 text-teal-400 flex items-center justify-center border border-teal-500/25 group-hover:scale-110 transition-transform">
                      <Zap className="w-5 h-5" />
                    </div>
                    <div>
                      <h3 className="font-bold text-on-surface text-base">Instant Waitlist Backfill</h3>
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        Immediately contacts priority waitlist patients when an appointment cancels to recover lost revenue.
                      </p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-teal-500/10 text-teal-400 border border-teal-500/20">
                    Revenue Recovery
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-on-surface-variant">Slot Date</label>
                    <input
                      type="text"
                      value={waitlistDate}
                      onChange={e => setWaitlistDate(e.target.value)}
                      placeholder="e.g. Tomorrow or Friday"
                      className="w-full px-3 py-1.5 rounded-lg bg-surface border border-outline/20 text-xs text-on-surface focus:outline-none focus:border-teal-500"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-on-surface-variant">Slot Time</label>
                    <input
                      type="text"
                      value={waitlistTime}
                      onChange={e => setWaitlistTime(e.target.value)}
                      placeholder="e.g. 10:30 AM"
                      className="w-full px-3 py-1.5 rounded-lg bg-surface border border-outline/20 text-xs text-on-surface focus:outline-none focus:border-teal-500"
                    />
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-surface-variant/40 border border-outline/5 flex items-center justify-between text-xs">
                  <span className="text-on-surface-variant">Active Waitlist Queue:</span>
                  <span className="font-bold text-teal-400">
                    {estimates?.campaigns?.waitlist?.queue_count || 1} waitlist patients pending opening
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-outline/10 flex items-center gap-2">
                <button
                  onClick={() => handleTriggerCampaign('waitlist')}
                  disabled={triggering['waitlist']}
                  className="flex-1 py-2.5 px-3 rounded-xl bg-teal-500/15 hover:bg-teal-500/25 text-teal-400 text-xs font-bold border border-teal-500/30 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                >
                  <Play className={`w-3.5 h-3.5 fill-current ${triggering['waitlist'] ? 'animate-spin' : ''}`} />
                  <span>{triggering['waitlist'] ? 'Dispatching...' : `Fill Open Slot (${waitlistDate} @ ${waitlistTime})`}</span>
                </button>

                <button
                  onClick={() => handleOpenTestModal('waitlist')}
                  className="p-2.5 rounded-xl border border-outline/20 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface transition-all"
                  title="Test Single Call"
                >
                  <PhoneForwarded className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* TAB 2: PUBLISHED GOAL RUNS (CALL-E API 0.6.0)                           */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {activeMainTab === 'goals' && (
        <div className="space-y-6 animate-in fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-on-surface flex items-center gap-2">
                <Target className="w-5 h-5 text-emerald-400" />
                Published Goal Runs (CALL-E 0.6.0 Protocol)
              </h2>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Trigger pre-configured, structured clinical outreach goals with dynamic patient variables.
              </p>
            </div>

            <span className="text-xs text-on-surface-variant/80 font-mono bg-surface-variant px-3 py-1 rounded-lg border border-outline/10">
              POST /calle/goals/{'{goal_id}'}/runs
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {goals.map((goal) => (
              <div
                key={goal.id}
                className="card p-5 flex flex-col justify-between hover:border-emerald-500/30 transition-all border border-outline/10 space-y-4"
              >
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded-md bg-surface-variant text-emerald-400 font-bold border border-outline/10">
                      {goal.id}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">
                      {goal.status || 'published'}
                    </span>
                  </div>

                  <h3 className="font-bold text-on-surface text-base">{goal.name}</h3>
                  <p className="text-xs text-on-surface-variant leading-relaxed">{goal.description}</p>

                  {goal.variables && Object.keys(goal.variables).length > 0 && (
                    <div className="space-y-1 pt-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-on-surface-variant">
                        Dynamic Schema Variables:
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(goal.variables).map(([k, desc]) => (
                          <span
                            key={k}
                            className="px-2 py-0.5 rounded-md bg-surface-variant/60 text-on-surface font-mono text-[10px] border border-outline/5"
                            title={String(desc)}
                          >
                            {k}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-outline/10">
                  <button
                    onClick={() => handleOpenGoalModal(goal)}
                    className="w-full py-2 px-3 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 text-xs font-bold border border-emerald-500/30 flex items-center justify-center gap-2 transition-all"
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Configure & Trigger Goal Run</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* TAB 3: LIVE OUTBOUND ACTIVITY FEED & INSPECTOR                          */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {(activeMainTab === 'feed' || activeMainTab === 'campaigns') && (
        <div className="card p-6 space-y-6 border border-outline/10">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-on-surface flex items-center gap-2">
                <PhoneCall className="w-5 h-5 text-emerald-400" />
                Live Outbound Call Records & Extraction Activity
              </h2>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Real-time log of CALL-E autonomous calls, structured extractions, and downstream appointment updates.
              </p>
            </div>

            {/* Filter Pills */}
            <div className="flex flex-wrap items-center gap-2">
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search ID, summary, notes..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                  className="pl-8 pr-3 py-1.5 rounded-xl bg-surface border border-outline/20 text-xs text-on-surface focus:outline-none focus:border-emerald-500 w-48 sm:w-60"
                />
              </div>

              <select
                value={statusFilter}
                onChange={e => setStatusFilter(e.target.value)}
                className="px-3 py-1.5 rounded-xl bg-surface border border-outline/20 text-xs text-on-surface focus:outline-none focus:border-emerald-500"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="running">Running</option>
                <option value="queued">Queued</option>
                <option value="failed">Failed</option>
              </select>

              <div className="flex items-center bg-surface-variant rounded-xl p-1 border border-outline/10 text-xs flex-wrap gap-1">
                {[
                  { id: 'all', label: 'All' },
                  { id: 'confirmation', label: 'Confirmation' },
                  { id: 'no_show', label: 'No-Show' },
                  { id: 'recall', label: 'Recall' },
                  { id: 'survey', label: 'Survey' },
                  { id: 'waitlist', label: 'Waitlist' },
                  { id: 'goal_run', label: 'Goal Run' },
                ].map(tab => (
                  <button
                    key={tab.id}
                    onClick={() => setFeedFilter(tab.id)}
                    className={`px-2.5 py-1 rounded-lg font-semibold text-[11px] transition-all ${
                      feedFilter === tab.id
                        ? 'bg-surface text-on-surface shadow-sm border border-outline/10'
                        : 'text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Calls Table */}
          {loading ? (
            <div className="py-12 text-center space-y-3">
              <RefreshCw className="w-6 h-6 text-emerald-400 animate-spin mx-auto" />
              <p className="text-xs text-on-surface-variant font-medium">Loading call activity feed...</p>
            </div>
          ) : filteredCalls.length === 0 ? (
            <div className="py-12 text-center rounded-xl border border-dashed border-outline/20 space-y-3">
              <PhoneCall className="w-8 h-8 text-on-surface-variant/40 mx-auto" />
              <p className="text-sm font-semibold text-on-surface">No outbound calls match this filter</p>
              <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
                Click any campaign card above or "Live Test Call" to execute an automated outbound outreach.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-outline/10 text-on-surface-variant font-bold uppercase tracking-wider text-[11px]">
                    <th className="py-3 px-4">Campaign</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Key Extracted Outcome</th>
                    <th className="py-3 px-4">Confidence</th>
                    <th className="py-3 px-4">CALL-E ID</th>
                    <th className="py-3 px-4">Timestamp</th>
                    <th className="py-3 px-4 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline/5">
                  {filteredCalls.map(c => {
                    const campaignColors = {
                      confirmation: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
                      no_show: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
                      recall: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
                      survey: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
                      waitlist: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
                      goal_run: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
                    };

                    const statusBadges = {
                      completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
                      running: 'bg-sky-500/10 text-sky-400 border-sky-500/20 animate-pulse',
                      queued: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
                      failed: 'bg-red-500/10 text-red-400 border-red-500/20',
                    };

                    const structured = c.structured_result || {};

                    return (
                      <tr key={c.id} className="hover:bg-surface-variant/30 transition-colors">
                        <td className="py-3.5 px-4 font-semibold text-on-surface">
                          <span
                            className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${
                              campaignColors[c.campaign_type] || 'bg-surface-variant text-on-surface-variant'
                            }`}
                          >
                            {c.campaign_type}
                          </span>
                        </td>

                        <td className="py-3.5 px-4">
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${
                              statusBadges[c.status] || 'bg-surface-variant text-on-surface-variant'
                            }`}
                          >
                            {c.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                            {c.status === 'running' && <Clock className="w-3 h-3 animate-spin" />}
                            {c.status === 'failed' && <AlertCircle className="w-3 h-3" />}
                            {c.status}
                          </span>
                        </td>

                        <td className="py-3.5 px-4 max-w-sm truncate text-on-surface-variant font-mono text-[11px]">
                          {structured.will_attend && (
                            <span className="text-emerald-400 font-bold">Conf: {structured.will_attend}</span>
                          )}
                          {structured.response_type && (
                            <span className="text-amber-400 font-bold">Resp: {structured.response_type}</span>
                          )}
                          {structured.interested && (
                            <span className="text-sky-400 font-bold">Interest: {structured.interested}</span>
                          )}
                          {structured.nps_score !== undefined && (
                            <span className="text-purple-400 font-bold">NPS: {structured.nps_score}/10</span>
                          )}
                          {structured.accepts_slot !== undefined && (
                            <span className="text-teal-400 font-bold">Accepted: {structured.accepts_slot ? 'Yes' : 'No'}</span>
                          )}
                          {!structured.will_attend &&
                            !structured.response_type &&
                            !structured.interested &&
                            structured.nps_score === undefined &&
                            structured.accepts_slot === undefined && (
                              <span className="text-on-surface-variant/70">{c.summary || 'Structured result verified'}</span>
                            )}
                        </td>

                        <td className="py-3.5 px-4 text-[11px]">
                          {c.completion_score !== null && c.completion_score !== undefined ? (
                            <span className="inline-flex items-center gap-1 text-emerald-400 font-bold">
                              {Math.round(c.completion_score * 100)}%
                              <span className="text-[10px] text-on-surface-variant/70 font-normal">({c.completion_label || 'high'})</span>
                            </span>
                          ) : (
                            <span className="text-on-surface-variant/40">—</span>
                          )}
                        </td>

                        <td className="py-3.5 px-4 font-mono text-[11px] text-on-surface-variant">
                          {c.calle_call_id ? c.calle_call_id.slice(0, 14) + '...' : 'Pending'}
                        </td>

                        <td className="py-3.5 px-4 text-on-surface-variant text-[11px]">
                          {c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'Just now'}
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => handleInspectCall(c)}
                            className="p-1.5 rounded-lg border border-outline/10 hover:bg-surface-variant text-on-surface-variant hover:text-on-surface transition-all"
                            title="Inspect Call & Structured Data"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* MODAL 1: SINGLE LIVE TEST CALL DISPATCHER                               */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {showSingleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
          <div className="card max-w-lg w-full p-6 space-y-6 relative border border-emerald-500/30 shadow-2xl max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowSingleModal(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <h3 className="text-lg font-bold text-on-surface flex items-center gap-2">
                <PhoneForwarded className="w-5 h-5 text-emerald-400" />
                Live Single Test Call Dispatcher
              </h3>
              <p className="text-xs text-on-surface-variant">
                Place an immediate test call via CALL-E SDK (<code className="text-emerald-400 font-mono">create_and_wait</code>) to any destination.
              </p>
            </div>

            {singleSubmitting ? (
              /* Live In-Progress State */
              <div className="py-8 text-center space-y-5 rounded-2xl bg-surface-variant/30 border border-emerald-500/20 p-6">
                <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
                  <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" />
                  <div className="relative w-12 h-12 rounded-full bg-emerald-500/30 flex items-center justify-center text-emerald-400">
                    <PhoneCall className="w-6 h-6 animate-pulse" />
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-bold text-on-surface text-base">CALL-E Active Phone Call In-Progress</h4>
                  <div className="flex flex-col items-center gap-1 text-xs text-on-surface-variant">
                    <p className="text-emerald-400 font-semibold flex items-center gap-1.5">
                      <RefreshCw className="w-3 h-3 animate-spin" />
                      {singleStep === 1 && '1/3 Initializing CALL-E SDK session & webhook...'}
                      {singleStep === 2 && '2/3 Dialing recipient phone line...'}
                      {singleStep === 3 && '3/3 Autonomous agent conversing & extracting JSON...'}
                    </p>
                    <p className="text-[11px] text-on-surface-variant/70">
                      Synchronously waiting for recipient call completion & structured extraction
                    </p>
                  </div>
                </div>
              </div>
            ) : singleResult ? (
              /* Result Completed View */
              <div className="space-y-4 rounded-xl bg-surface-variant/30 border border-emerald-500/25 p-4">
                <div className="flex items-center justify-between border-b border-outline/10 pb-3">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <h4 className="font-bold text-on-surface text-sm">Call Completed & Extracted</h4>
                  </div>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase">
                    Status: {singleResult.status}
                  </span>
                </div>

                <div className="space-y-2 text-xs">
                  <p className="text-on-surface-variant">
                    <strong className="text-on-surface">Summary:</strong> {singleResult.summary || 'Call finished successfully.'}
                  </p>
                  <div>
                    <div className="flex items-center justify-between text-[11px] font-bold text-on-surface mb-1">
                      <span>Extracted JSON Schema Result:</span>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(JSON.stringify(singleResult.structured_result || {}, null, 2));
                          setSingleCopied(true);
                          setTimeout(() => setSingleCopied(false), 2000);
                        }}
                        className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-mono"
                      >
                        {singleCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        <span>{singleCopied ? 'Copied' : 'Copy JSON'}</span>
                      </button>
                    </div>
                    <pre className="p-3 rounded-lg bg-surface border border-outline/10 text-emerald-400 font-mono text-[11px] overflow-x-auto">
                      {JSON.stringify(singleResult.structured_result || {}, null, 2)}
                    </pre>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setSingleResult(null)}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-surface-variant text-on-surface hover:bg-surface-variant/80"
                  >
                    Test Another Call
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowSingleModal(false)}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-[#1a3a2e]"
                    style={{ backgroundColor: '#7FCD4D' }}
                  >
                    Done & View Feed
                  </button>
                </div>
              </div>
            ) : (
              /* Input Form */
              <form onSubmit={handleSingleCallSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-on-surface mb-1">Campaign Type</label>
                  <select
                    value={singleCampaign}
                    onChange={e => {
                      setSingleCampaign(e.target.value);
                      if (e.target.value !== 'confirmation') {
                        setSingleAppointmentId('');
                      }
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                  >
                    <option value="confirmation">1. 24-Hour Appointment Confirmation</option>
                    <option value="no_show">2. 2-Hour Post-No-Show Recovery</option>
                    <option value="recall">3. 30/60/90-Day Patient Recall</option>
                    <option value="survey">4. Post-Visit Satisfaction Survey (NPS)</option>
                    <option value="waitlist">5. Instant Waitlist Backfill</option>
                  </select>
                </div>

                {/* Recipient Source Mode Selection */}
                <div>
                  <label className="block text-xs font-semibold text-on-surface mb-1.5">Recipient Source</label>
                  <div className="grid grid-cols-2 gap-2 p-1 bg-surface-variant/40 rounded-xl border border-outline/10">
                    <button
                      type="button"
                      onClick={() => {
                        setSingleSource('existing');
                        if (appointmentsList.length > 0) {
                          handleSelectAppt(appointmentsList[0].id);
                        }
                      }}
                      className={`py-1.5 px-3 rounded-lg text-xs font-bold transition-all ${
                        singleSource === 'existing'
                          ? 'bg-surface text-on-surface shadow-sm border border-outline/20'
                          : 'text-on-surface-variant hover:text-on-surface'
                      }`}
                    >
                      📅 Scheduled Appointment
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSingleSource('custom');
                        setSingleAppointmentId('');
                        setSinglePatientId('');
                      }}
                      className={`py-1.5 px-3 rounded-lg text-xs font-bold transition-all ${
                        singleSource === 'custom'
                          ? 'bg-surface text-on-surface shadow-sm border border-outline/20'
                          : 'text-on-surface-variant hover:text-on-surface'
                      }`}
                    >
                      📱 Custom Phone Number
                    </button>
                  </div>
                </div>

                {singleSource === 'existing' ? (
                  <div>
                    <label className="block text-xs font-semibold text-on-surface mb-1">
                      Select Scheduled Appointment
                    </label>
                    <select
                      value={singleAppointmentId}
                      onChange={e => handleSelectAppt(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                    >
                      <option value="">-- Choose appointment from calendar ({appointmentsList.length} available) --</option>
                      {appointmentsList.map(appt => (
                        <option key={appt.id} value={appt.id}>
                          {appt.patient_name || 'Patient'} — {appt.datetime ? appt.datetime.slice(0, 16).replace('T', ' ') : 'No time'} ({appt.status}) — {appt.patient_phone || 'No phone'}
                        </option>
                      ))}
                    </select>
                    {singleAppointmentId && (
                      <div className="mt-2 p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-[11px] text-emerald-800 space-y-0.5">
                        <p className="font-bold">Patient: {singlePatientName || 'Patient'}</p>
                        <p>Phone: <span className="font-mono">{singlePhone}</span></p>
                        <p>Scheduled: {singleTime || 'Tomorrow'}</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-xs font-semibold text-on-surface mb-1">Patient Name</label>
                        <input
                          type="text"
                          placeholder="e.g. Alex Johnson"
                          value={singlePatientName}
                          onChange={e => setSinglePatientName(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-on-surface mb-1">
                          Phone Number (E.164)
                        </label>
                        <input
                          type="text"
                          required
                          placeholder="+14155552671"
                          value={singlePhone}
                          onChange={e => setSinglePhone(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    </div>
                    {singleCampaign === 'confirmation' && (
                      <div>
                        <label className="block text-xs font-semibold text-on-surface mb-1">Appointment Time</label>
                        <input
                          type="text"
                          value={singleTime}
                          onChange={e => setSingleTime(e.target.value)}
                          placeholder="e.g. Wednesday, Aug 26 at 10:30 AM (Auto-scheduled if empty)"
                          className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                        />
                        <p className="text-[11px] text-on-surface-variant/70 mt-1">
                          💡 System will atomically create a real appointment and link this call to the database.
                        </p>
                      </div>
                    )}
                  </>
                )}

                {singleCampaign === 'recall' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-on-surface mb-1">Recall Threshold</label>
                      <select
                        value={singleRecallDays}
                        onChange={e => setSingleRecallDays(Number(e.target.value))}
                        className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                      >
                        <option value={30}>30 Days Overdue</option>
                        <option value={60}>60 Days Overdue</option>
                        <option value={90}>90 Days Overdue</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-on-surface mb-1">Recall Type</label>
                      <input
                        type="text"
                        value={singleRecallType}
                        onChange={e => setSingleRecallType(e.target.value)}
                        placeholder="Routine follow-up"
                        className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                  </div>
                )}

                {singleCampaign === 'waitlist' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-on-surface mb-1">Open Slot Date</label>
                      <input
                        type="text"
                        value={singleSlotDate}
                        onChange={e => setSingleSlotDate(e.target.value)}
                        placeholder="Tomorrow"
                        className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-on-surface mb-1">Open Slot Time</label>
                      <input
                        type="text"
                        value={singleSlotTime}
                        onChange={e => setSingleSlotTime(e.target.value)}
                        placeholder="10:30 AM"
                        className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                  </div>
                )}

                {/* Engine Selector: Instant 1s Ring vs CALL-E Agent */}
                <div className="space-y-2">
                  <label className="block text-xs font-semibold text-on-surface">Telephony Dispatch Engine</label>
                  <div className="grid grid-cols-2 gap-2.5">
                    <button
                      type="button"
                      onClick={() => setSingleEngine('instant')}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        singleEngine === 'instant'
                          ? 'border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/30'
                          : 'border-outline/20 bg-surface hover:bg-surface-variant/40'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                          ⚡ Instant Direct Dial
                        </span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400">
                          1s Ring
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant leading-relaxed">
                        Direct Retell / Telnyx SIP ring. Bell rings on your phone within 1-2 seconds.
                      </p>
                    </button>

                    <button
                      type="button"
                      onClick={() => setSingleEngine('calle')}
                      className={`p-3 rounded-xl border text-left transition-all ${
                        singleEngine === 'calle'
                          ? 'border-emerald-500 bg-emerald-500/10 ring-1 ring-emerald-500/30'
                          : 'border-outline/20 bg-surface hover:bg-surface-variant/40'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-bold text-on-surface flex items-center gap-1.5">
                          🤖 CALL-E Agent
                        </span>
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">
                          Hackathon
                        </span>
                      </div>
                      <p className="text-[11px] text-on-surface-variant leading-relaxed">
                        Autonomous CALL-E LLM agent with real-time goal planning and structured schema.
                      </p>
                    </button>
                  </div>
                </div>

                <div className="p-3 rounded-xl bg-surface-variant/30 border border-outline/10 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <p className="text-xs font-bold text-on-surface">Wait for Call Completion</p>
                    <p className="text-[11px] text-on-surface-variant">
                      Hold browser connection open until caller hangs up (Turn OFF for instant 1s dispatch)
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={singleWaitForResult}
                    onChange={e => setSingleWaitForResult(e.target.checked)}
                    className="w-4 h-4 rounded text-emerald-500 focus:ring-emerald-500"
                  />
                </div>

                <div className="pt-2 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setShowSingleModal(false)}
                    className="px-4 py-2.5 rounded-xl border border-outline/20 text-xs font-bold text-on-surface-variant hover:bg-surface-variant"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2.5 rounded-xl text-xs font-bold text-[#1a3a2e] transition-all flex items-center gap-2 shadow-lg"
                    style={{ backgroundColor: '#7FCD4D' }}
                  >
                    <PhoneCall className="w-3.5 h-3.5" />
                    <span>Place Live Call Now</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* MODAL 2: PUBLISHED GOAL RUN EXECUTOR (CALL-E 0.6.0)                    */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {showGoalModal && selectedGoal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
          <div className="card max-w-lg w-full p-6 space-y-6 relative border border-emerald-500/30 shadow-2xl max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowGoalModal(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <span className="px-2 py-0.5 rounded-md bg-surface-variant text-emerald-400 font-mono text-[10px] font-bold">
                Goal ID: {selectedGoal.id}
              </span>
              <h3 className="text-lg font-bold text-on-surface">{selectedGoal.name}</h3>
              <p className="text-xs text-on-surface-variant">{selectedGoal.description}</p>
            </div>

            {goalSubmitting ? (
              <div className="py-8 text-center space-y-4 rounded-xl bg-surface-variant/30 border border-emerald-500/20">
                <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin mx-auto" />
                <p className="text-xs font-bold text-on-surface">Executing Goal Run on CALL-E API 0.6.0...</p>
              </div>
            ) : goalResult ? (
              <div className="space-y-4 rounded-xl bg-surface-variant/30 border border-emerald-500/25 p-4 text-xs">
                <div className="flex items-center justify-between border-b border-outline/10 pb-2">
                  <span className="font-bold text-emerald-400">Goal Run Complete</span>
                  <span className="font-mono text-[11px] text-on-surface-variant">ID: {goalResult.goal_run?.id || goalResult.record_id}</span>
                </div>
                <pre className="p-3 rounded-lg bg-surface border border-outline/10 text-emerald-400 font-mono text-[11px] overflow-x-auto">
                  {JSON.stringify(goalResult.goal_run || goalResult, null, 2)}
                </pre>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    onClick={() => setShowGoalModal(false)}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-[#1a3a2e]"
                    style={{ backgroundColor: '#7FCD4D' }}
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleGoalRunSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-on-surface mb-1">
                    Recipient Phone Number (E.164 format)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="+1XXXXXXXXXX"
                    value={goalPhone}
                    onChange={e => setGoalPhone(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-outline/20 bg-surface text-on-surface text-sm focus:outline-none focus:border-emerald-500"
                  />
                </div>

                {selectedGoal.variables && Object.keys(selectedGoal.variables).length > 0 && (
                  <div className="space-y-3 pt-1">
                    <p className="text-xs font-bold text-on-surface">Goal Variables:</p>
                    {Object.entries(selectedGoal.variables).map(([k, desc]) => (
                      <div key={k}>
                        <label className="block text-[11px] font-semibold text-on-surface-variant mb-1">
                          {k} <span className="text-[10px] text-on-surface-variant/60">({String(desc)})</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={goalVariables[k] || ''}
                          onChange={e => setGoalVariables(prev => ({ ...prev, [k]: e.target.value }))}
                          placeholder={`Enter ${k}`}
                          className="w-full px-3 py-2 rounded-xl border border-outline/20 bg-surface text-on-surface text-xs focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    ))}
                  </div>
                )}

                <div className="pt-2 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setShowGoalModal(false)}
                    className="px-4 py-2.5 rounded-xl border border-outline/20 text-xs font-bold text-on-surface-variant hover:bg-surface-variant"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2.5 rounded-xl text-xs font-bold text-[#1a3a2e] transition-all flex items-center gap-2 shadow-lg"
                    style={{ backgroundColor: '#7FCD4D' }}
                  >
                    <Send className="w-3.5 h-3.5" />
                    <span>Run Goal Now</span>
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* MODAL 3: CALL DETAIL INSPECTOR & STRUCTURED OUTPUT VIEWER              */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {selectedCall && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
          <div className="card max-w-2xl w-full p-6 space-y-6 relative border border-outline/20 shadow-2xl max-h-[88vh] overflow-y-auto">
            <button
              onClick={() => setSelectedCall(null)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                  {selectedCall.campaign_type}
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider bg-surface-variant text-on-surface-variant">
                  Status: {selectedCall.status}
                </span>
              </div>
              <h3 className="text-lg font-bold text-on-surface">Call Result & Structured Data Inspection</h3>
            </div>

            <div className="space-y-4 text-xs">
              {/* Summary Box */}
              <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/10 space-y-1">
                <p className="font-semibold text-on-surface">Call Summary</p>
                <p className="text-on-surface-variant leading-relaxed">
                  {selectedCall.summary || 'No summary available for this call.'}
                </p>
              </div>

              {/* Confidence Meter */}
              {selectedCall.completion_score !== null && selectedCall.completion_score !== undefined && (
                <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/10 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-on-surface">CALL-E Confidence Score</span>
                    <span className="font-bold text-emerald-400">
                      {Math.round(selectedCall.completion_score * 100)}% ({selectedCall.completion_label || 'high'})
                    </span>
                  </div>
                  <div className="w-full bg-surface-variant rounded-full h-2 overflow-hidden border border-outline/10">
                    <div
                      className="bg-emerald-400 h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.round(selectedCall.completion_score * 100)}%` }}
                    />
                  </div>
                </div>
              )}

              {/* Structured JSON Output */}
              <div>
                <div className="flex items-center justify-between text-xs font-semibold text-on-surface mb-2">
                  <span>Structured Extraction (CALL-E JSON Output)</span>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(selectedCall.structured_result || {}, null, 2));
                      setInspectorCopied(true);
                      setTimeout(() => setInspectorCopied(false), 2000);
                    }}
                    className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-mono text-[11px]"
                  >
                    {inspectorCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    <span>{inspectorCopied ? 'Copied' : 'Copy JSON'}</span>
                  </button>
                </div>
                <pre className="p-4 rounded-xl bg-surface border border-outline/10 text-emerald-400 font-mono text-xs overflow-x-auto leading-relaxed">
                  {JSON.stringify(selectedCall.structured_result || {}, null, 2)}
                </pre>
              </div>

              {/* Downstream Actions Log */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-surface-variant/30 border border-outline/5">
                  <p className="text-on-surface-variant">CALL-E ID</p>
                  <p className="font-mono text-on-surface font-semibold truncate mt-0.5">
                    {selectedCall.calle_call_id || 'N/A'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-surface-variant/30 border border-outline/5">
                  <p className="text-on-surface-variant">Task Completed</p>
                  <p className="font-semibold text-emerald-400 mt-0.5">
                    {selectedCall.task_completed ? 'Yes (100%)' : 'Pending / No'}
                  </p>
                </div>
              </div>

              {/* Developer Call Events (if available) */}
              {callEvents.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-outline/10">
                  <p className="font-semibold text-on-surface">Developer Call Event Stream</p>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {callEvents.map((ev, i) => (
                      <div key={ev.id || i} className="p-2 rounded-lg bg-surface border border-outline/5 font-mono text-[10px] text-on-surface-variant flex items-center justify-between">
                        <span className="text-emerald-400 font-bold">{ev.type}</span>
                        <span>{ev.data?.message || JSON.stringify(ev.data)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OutboundCampaigns;
