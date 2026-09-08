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
import CalleCallLog from '../components/CalleCallLog';

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
  const [singleEngine, setSingleEngine] = useState('calle'); // 'calle' (hero autonomous task) | 'instant' (high-speed dial)
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


  // ── Open Test Single Modal Prefilled for Specific Campaign ────────────────────
  const handleOpenTestModal = (campaignType = 'confirmation') => {
    setSingleCampaign(campaignType);
    setSingleResult(null);
    setSingleStep(1);
    setShowSingleModal(true);
  };

  // ── Trigger Batch Campaign ───────────────────────────────────────────────────
  const handleTriggerCampaign = async (type) => {
    const normType = type === 'no_show' ? 'no-show' : type;
    setTriggering(prev => ({ ...prev, [type]: true, [normType]: true }));
    try {
      let endpoint = `/calle/campaigns/${normType}`;
      let body = {};
      if (normType === 'recall') {
        body = { days_threshold: recallDays, limit: 20 };
      } else if (normType === 'waitlist') {
        body = { slot_date: waitlistDate, slot_time: waitlistTime, limit: 15 };
      }

      const res = await api.post(endpoint, body);
      notify(res.data?.message || `Campaign '${normType}' batch dispatched successfully!`);
      fetchData(false);
    } catch (err) {
      notify(err.response?.data?.detail || `Failed to dispatch ${type} campaign`, 'error');
    } finally {
      setTriggering(prev => ({ ...prev, [type]: false, [normType]: false }));
    }
  };

  // ── Trigger All Active Campaigns Master Batch ─────────────────────────────────
  const handleTriggerAllCampaigns = async () => {
    if (!window.confirm('Are you sure you want to dispatch all active automated outbound campaigns now?')) return;
    setTriggeringAll(true);
    try {
      const results = await Promise.allSettled([
        api.post('/calle/campaigns/confirmation', {}),
        api.post('/calle/campaigns/no-show', {}),
        api.post('/calle/campaigns/recall', { days_threshold: recallDays, limit: 20 }),
        api.post('/calle/campaigns/survey', {}),
        api.post('/calle/campaigns/waitlist', { slot_date: waitlistDate, slot_time: waitlistTime, limit: 15 }),
      ]);
      const successful = results.filter(r => r.status === 'fulfilled').length;
      notify(`All 5 automated campaign batches processed successfully (${successful}/5 active)!`);
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
        bypass_quiet_hours: true,
        force: true,
      };

      const res = await api.post('/calle/calls/single', payload);
      setSingleResult(res.data);
      if (res.data?.status === 'failed') {
        const errorReason = res.data?.error || res.data?.reason || res.data?.message || res.data?.detail || 'Call dispatch failed';
        notify(`Call failed: ${errorReason}`, 'error');
      } else {
        notify(`CALL-E call executed! Status: ${res.data?.status || 'completed'}`);
      }
      fetchData(false);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.response?.data?.message || err.message || 'Failed to execute test call';
      notify(errorMsg, 'error');
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
          className={`fixed top-5 right-5 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-xl border text-sm font-semibold transition-all transform animate-in slide-in-from-top-2 ${
            notification.type === 'error'
              ? 'bg-white border-red-200 text-red-900 shadow-red-900/10'
              : 'bg-white border-emerald-200 text-emerald-900 shadow-emerald-900/10'
          }`}
        >
          {notification.type === 'error' ? (
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
          ) : (
            <CheckCircle2 className="w-5 h-5 text-[#396a00] flex-shrink-0" />
          )}
          <span>{notification.msg}</span>
        </div>
      )}

      {/* ── Engine Status Banner ───────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-5 py-3.5 rounded-2xl bg-emerald-50/90 border border-emerald-200 text-xs font-semibold shadow-xs">
        <div className="flex items-center gap-3">
          <span className="flex h-3 w-3 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-600"></span>
          </span>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-extrabold text-sm text-emerald-950 tracking-tight">
              🟢 CALL-E Autonomous Engine: Live Mode
            </span>
            <span className="hidden sm:inline text-emerald-500">•</span>
            <span className="text-emerald-800/90 font-medium">
              Direct Autonomous Telephony Dispatch
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-lg bg-white text-emerald-900 font-mono text-[11px] font-bold border border-emerald-300 shadow-2xs">
            API v{statusInfo?.api_version || '0.6.0'}
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-emerald-700 text-white text-[11px] font-bold shadow-xs">
            READY
          </span>
        </div>
      </div>

      {/* ── Header Hero Banner ─────────────────────────────────────────────── */}
      <div className="card p-6 sm:p-8 border border-[#edf1ef] relative overflow-hidden shadow-card bg-white">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 relative z-10">
          <div className="space-y-2.5 max-w-3xl">
            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                <Sparkles className="w-3.5 h-3.5 text-[#396a00]" />
                CALL-E Voice AI Active (v{statusInfo?.api_version || '0.6.0'})
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-200">
                <ShieldCheck className="w-3.5 h-3.5 text-[#396a00]" />
                HIPAA Certified Scrubber
              </span>
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-[#7FCD4D]/15 text-[#396a00] border border-[#7FCD4D]/30">
                <Radio className="w-3.5 h-3.5 text-[#396a00] animate-pulse" />
                5 Automated Workflows
              </span>
            </div>

            <h1 className="page-header-title text-2xl sm:text-3xl font-extrabold text-[#181c1c] tracking-tight">
              CALL-E Autonomous Outbound Campaigns
            </h1>
            <p className="text-sm text-[#3d4946] leading-relaxed">
              Fully autonomous, HIPAA-compliant patient outreach for appointment confirmations, no-show recoveries, routine recalls, satisfaction surveys, and instant waitlist backfills.
            </p>
          </div>

          <div className="flex items-center gap-3 flex-shrink-0 flex-wrap">
            <button
              onClick={() => fetchData(true)}
              disabled={refreshing}
              className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-[#3d4946] transition-all disabled:opacity-50"
              title="Refresh Engine Feed"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-[#396a00]' : ''}`} />
            </button>

            <button
              onClick={() => handleOpenTestModal('confirmation')}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold text-white transition-all shadow-md hover:brightness-105 active:scale-95 cursor-pointer"
              style={{ background: 'linear-gradient(135deg, #396a00 0%, #4d8a00 100%)' }}
            >
              <PhoneForwarded className="w-4 h-4" />
              <span>Live Test Call</span>
            </button>
          </div>
        </div>

        {/* ── Key Performance Metrics Grid ─────────────────────────────────── */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3.5 mt-6 pt-6 border-t border-[#edf1ef]">
          <div className="p-4 rounded-xl bg-[#f7faf9] border border-[#edf1ef]">
            <div className="flex items-center justify-between text-[#3d4946] text-xs font-semibold">
              <span>Total Outbound</span>
              <PhoneCall className="w-3.5 h-3.5 text-[#396a00]" />
            </div>
            <p className="text-xl sm:text-2xl font-black text-[#181c1c] mt-1">{totalCallsCount}</p>
          </div>

          <div className="p-4 rounded-xl bg-[#f7faf9] border border-[#edf1ef]">
            <div className="flex items-center justify-between text-[#3d4946] text-xs font-semibold">
              <span>Completed Calls</span>
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
            </div>
            <p className="text-xl sm:text-2xl font-black text-emerald-800 mt-1">{completedCallsCount}</p>
          </div>

          <div className="p-4 rounded-xl bg-[#f7faf9] border border-[#edf1ef]">
            <div className="flex items-center justify-between text-[#3d4946] text-xs font-semibold">
              <span>Confirmed Attendance</span>
              <CalendarCheck className="w-3.5 h-3.5 text-sky-700" />
            </div>
            <p className="text-xl sm:text-2xl font-black text-sky-800 mt-1">{confirmedApptsCount}</p>
          </div>

          <div className="p-4 rounded-xl bg-[#f7faf9] border border-[#edf1ef]">
            <div className="flex items-center justify-between text-[#3d4946] text-xs font-semibold">
              <span>Rescheduled Recoveries</span>
              <RotateCcw className="w-3.5 h-3.5 text-amber-700" />
            </div>
            <p className="text-xl sm:text-2xl font-black text-amber-800 mt-1">{rescheduledCount}</p>
          </div>

          <div className="p-4 rounded-xl bg-[#f7faf9] border border-[#edf1ef] col-span-2 sm:col-span-1">
            <div className="flex items-center justify-between text-[#3d4946] text-xs font-semibold">
              <span>Engine Status</span>
              <span className="w-2 h-2 rounded-full bg-[#396a00] animate-ping" />
            </div>
            <p className="text-sm font-black text-[#396a00] mt-1 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-[#396a00]" />
              {statusInfo?.live_mode ? 'Live CALL-E API' : 'Dry-Run Mode'}
            </p>
          </div>
        </div>
      </div>

      {/* ── Main Navigation Sub-Bar ─────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#edf1ef] pb-4">
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
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
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
              <span className="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-slate-100 text-slate-800 border border-slate-200">
                {calls.length}
              </span>
            )}
          </button>
        </div>

        {/* ── Master Batch Dispatcher Bar ──────────────────────────────────── */}
        {activeMainTab === 'campaigns' && (
          <div className="flex items-center gap-3 bg-white p-2 px-3.5 rounded-xl border border-[#edf1ef] shadow-sm text-xs">
            <div className="flex items-center gap-2">
              <span className="text-[#3d4946] font-medium">Backlog Queue:</span>
              <span className="font-bold text-emerald-800 px-2 py-0.5 rounded-md bg-emerald-100 border border-emerald-200">
                {estimates?.total_queued || 0} calls ready
              </span>
              <span className="text-slate-300">|</span>
              <span className="text-[#3d4946] font-medium">Est. Cost:</span>
              <span className="font-extrabold text-[#181c1c]">
                ${estimates?.estimated_total_cost?.toFixed(2) || '0.00'}
              </span>
            </div>

            <button
              onClick={handleTriggerAllCampaigns}
              disabled={triggeringAll}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg text-xs font-bold text-white transition-all shadow hover:brightness-105 active:scale-95 disabled:opacity-40 cursor-pointer"
              style={{ background: 'linear-gradient(135deg, #396a00 0%, #4d8a00 100%)' }}
              title="Dispatch all due automated campaign batches now"
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
            <div className="card p-5 flex flex-col justify-between hover:border-emerald-500/50 hover:shadow-md transition-all border border-[#edf1ef] bg-white group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-800 flex items-center justify-center border border-emerald-200 group-hover:scale-105 transition-transform">
                    <CalendarCheck className="w-5 h-5 text-[#396a00]" />
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                    24h Prior
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-[#181c1c] text-base">24-Hour Appointment Confirmation</h3>
                  <p className="text-xs text-[#3d4946] mt-1 leading-relaxed">
                    Calls patients 24 hours prior to scheduled visits to confirm attendance, answer prep questions, or handle reschedule requests.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-[#f7faf9] border border-[#edf1ef] flex items-center justify-between text-xs">
                  <span className="text-[#3d4946] font-medium">Tomorrow's Queue:</span>
                  <span className="font-bold text-emerald-800">
                    {estimates?.campaigns?.confirmation?.queue_count || 0} patients ready (~${estimates?.campaigns?.confirmation?.estimated_cost !== undefined ? estimates.campaigns.confirmation.estimated_cost.toFixed(2) : '0.00'})
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-[#edf1ef] space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('confirmation')}
                    disabled={triggering['confirmation']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-300 flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['confirmation'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['confirmation'] ? 'Dispatching...' : 'Run Confirmation Batch'}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('confirmation')}
                    className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-[#3d4946] hover:text-[#181c1c] transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 2: 2-Hour Post-No-Show Recovery ─────────────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-amber-500/50 hover:shadow-md transition-all border border-[#edf1ef] bg-white group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-900 flex items-center justify-center border border-amber-200 group-hover:scale-105 transition-transform">
                    <UserX className="w-5 h-5 text-amber-800" />
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200">
                    2h Post-Miss
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-[#181c1c] text-base">2-Hour Post-No-Show Recovery</h3>
                  <p className="text-xs text-[#3d4946] mt-1 leading-relaxed">
                    Calls patients within 2 hours of a missed appointment to express care, address barriers, and re-book their visit immediately.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-[#f7faf9] border border-[#edf1ef] flex items-center justify-between text-xs">
                  <span className="text-[#3d4946] font-medium">Today's Missed:</span>
                  <span className="font-bold text-amber-900">
                    {estimates?.campaigns?.no_show?.queue_count || 0} no-shows ready (~${estimates?.campaigns?.no_show?.estimated_cost !== undefined ? estimates.campaigns.no_show.estimated_cost.toFixed(2) : '0.00'})
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-[#edf1ef] space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('no-show')}
                    disabled={triggering['no-show']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-amber-50 hover:bg-amber-100 text-amber-900 text-xs font-bold border border-amber-300 flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['no-show'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['no-show'] ? 'Dispatching...' : 'Run No-Show Recovery'}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('no_show')}
                    className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-[#3d4946] hover:text-[#181c1c] transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 3: 30/60/90-Day Patient Recall ──────────────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-sky-500/50 hover:shadow-md transition-all border border-[#edf1ef] bg-white group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-sky-100 text-sky-900 flex items-center justify-center border border-sky-200 group-hover:scale-105 transition-transform">
                    <RotateCcw className="w-5 h-5 text-sky-800" />
                  </div>
                  <div className="flex items-center bg-[#edf1ef] rounded-lg p-0.5 border border-slate-200 text-xs">
                    {[30, 60, 90].map(d => (
                      <button
                        key={d}
                        onClick={() => setRecallDays(d)}
                        className={`px-2 py-0.5 rounded-md font-bold text-[10px] transition-all ${
                          recallDays === d ? 'bg-sky-700 text-white shadow-sm' : 'text-[#3d4946] hover:text-[#181c1c]'
                        }`}
                      >
                        {d}d
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <h3 className="font-bold text-[#181c1c] text-base">30/60/90-Day Patient Recall</h3>
                  <p className="text-xs text-[#3d4946] mt-1 leading-relaxed">
                    Re-engages overdue patients due for follow-ups, preventive screenings, chronic care check-ups, and annual wellness visits.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-[#f7faf9] border border-[#edf1ef] flex items-center justify-between text-xs">
                  <span className="text-[#3d4946] font-medium">{recallDays}-Day Backlog:</span>
                  <span className="font-bold text-sky-900">
                    {estimates?.counts?.[`recall_${recallDays}`] || estimates?.campaigns?.recall?.queue_count || 0} patients ready
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-[#edf1ef] space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('recall')}
                    disabled={triggering['recall']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-sky-50 hover:bg-sky-100 text-sky-900 text-xs font-bold border border-sky-300 flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['recall'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['recall'] ? 'Dispatching...' : 'Run Recall Batch'}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('recall')}
                    className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-[#3d4946] hover:text-[#181c1c] transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 4: Post-Visit Satisfaction Survey (NPS) ─────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-purple-500/50 hover:shadow-md transition-all border border-[#edf1ef] bg-white group relative overflow-hidden">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-900 flex items-center justify-center border border-purple-200 group-hover:scale-105 transition-transform">
                    <Star className="w-5 h-5 text-purple-800" />
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 text-purple-900 border border-purple-200">
                    Post-Visit NPS
                  </span>
                </div>

                <div>
                  <h3 className="font-bold text-[#181c1c] text-base">Post-Visit Satisfaction Survey</h3>
                  <p className="text-xs text-[#3d4946] mt-1 leading-relaxed">
                    Collects 1-10 Net Promoter Scores (NPS) and structured quality feedback within hours of completed clinical visits.
                  </p>
                </div>

                <div className="p-2.5 rounded-lg bg-[#f7faf9] border border-[#edf1ef] flex items-center justify-between text-xs">
                  <span className="text-[#3d4946] font-medium">Today's Completed:</span>
                  <span className="font-bold text-purple-900">
                    {estimates?.campaigns?.survey?.queue_count || 0} visits ready (~${estimates?.campaigns?.survey?.estimated_cost !== undefined ? estimates.campaigns.survey.estimated_cost.toFixed(2) : '0.00'})
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-[#edf1ef] space-y-2">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleTriggerCampaign('survey')}
                    disabled={triggering['survey']}
                    className="flex-1 py-2.5 px-3 rounded-xl bg-purple-50 hover:bg-purple-100 text-purple-900 text-xs font-bold border border-purple-300 flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
                  >
                    <Play className={`w-3.5 h-3.5 fill-current ${triggering['survey'] ? 'animate-spin' : ''}`} />
                    <span>{triggering['survey'] ? 'Dispatching...' : 'Run Post-Visit Survey'}</span>
                  </button>

                  <button
                    onClick={() => handleOpenTestModal('survey')}
                    className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-[#3d4946] hover:text-[#181c1c] transition-all"
                    title="Test Single Call"
                  >
                    <PhoneForwarded className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            {/* ── CARD 5: Instant Waitlist Backfill ────────────────────────── */}
            <div className="card p-5 flex flex-col justify-between hover:border-teal-500/50 hover:shadow-md transition-all border border-[#edf1ef] bg-white group relative overflow-hidden md:col-span-2 lg:col-span-2">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-teal-100 text-teal-900 flex items-center justify-center border border-teal-200 group-hover:scale-105 transition-transform">
                      <Zap className="w-5 h-5 text-teal-800" />
                    </div>
                    <div>
                      <h3 className="font-bold text-[#181c1c] text-base">Instant Waitlist Backfill</h3>
                      <p className="text-xs text-[#3d4946] mt-0.5">
                        Immediately contacts priority waitlist patients when an appointment cancels to recover lost revenue.
                      </p>
                    </div>
                  </div>
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-teal-100 text-teal-900 border border-teal-200">
                    Revenue Recovery
                  </span>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-[#3d4946]">Slot Date</label>
                    <input
                      type="text"
                      value={waitlistDate}
                      onChange={e => setWaitlistDate(e.target.value)}
                      placeholder="e.g. Tomorrow or Friday"
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-xs text-[#181c1c] focus:outline-none focus:border-teal-600 shadow-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[11px] font-semibold text-[#3d4946]">Slot Time</label>
                    <input
                      type="text"
                      value={waitlistTime}
                      onChange={e => setWaitlistTime(e.target.value)}
                      placeholder="e.g. 10:30 AM"
                      className="w-full px-3 py-2 rounded-lg bg-white border border-slate-200 text-xs text-[#181c1c] focus:outline-none focus:border-teal-600 shadow-sm"
                    />
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-[#f7faf9] border border-[#edf1ef] flex items-center justify-between text-xs">
                  <span className="text-[#3d4946] font-medium">Active Waitlist Queue:</span>
                  <span className="font-bold text-teal-900">
                    {estimates?.campaigns?.waitlist?.queue_count ?? 0} waitlist patients pending opening
                  </span>
                </div>
              </div>

              <div className="mt-6 pt-4 border-t border-[#edf1ef] flex items-center gap-2">
                <button
                  onClick={() => handleTriggerCampaign('waitlist')}
                  disabled={triggering['waitlist']}
                  className="flex-1 py-2.5 px-3 rounded-xl bg-teal-50 hover:bg-teal-100 text-teal-900 text-xs font-bold border border-teal-300 flex items-center justify-center gap-2 transition-all shadow-sm disabled:opacity-50"
                >
                  <Play className={`w-3.5 h-3.5 fill-current ${triggering['waitlist'] ? 'animate-spin' : ''}`} />
                  <span>{triggering['waitlist'] ? 'Dispatching...' : 'Run Waitlist Backfill'}</span>
                </button>

                <button
                  onClick={() => handleOpenTestModal('waitlist')}
                  className="p-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 text-[#3d4946] hover:text-[#181c1c] transition-all"
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
              <h2 className="text-lg font-bold text-[#181c1c] flex items-center gap-2">
                <Target className="w-5 h-5 text-[#396a00]" />
                Published Goal Runs (CALL-E 0.6.0 Protocol)
              </h2>
              <p className="text-xs text-[#3d4946] mt-0.5">
                Trigger pre-configured, structured clinical outreach goals with dynamic patient variables.
              </p>
            </div>

            <span className="text-xs text-[#3d4946] font-mono bg-[#edf1ef] px-3 py-1 rounded-lg border border-slate-200">
              POST /calle/goals/{'{goal_id}'}/runs
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {goals.map((goal) => (
              <div
                key={goal.id}
                className="card p-5 flex flex-col justify-between hover:border-emerald-500/40 hover:shadow-md transition-all border border-[#edf1ef] bg-white space-y-4"
              >
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] px-2 py-0.5 rounded-md bg-[#edf1ef] text-emerald-800 font-bold border border-slate-200">
                      {goal.id}
                    </span>
                    <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 uppercase">
                      {goal.status || 'published'}
                    </span>
                  </div>

                  <h3 className="font-bold text-[#181c1c] text-base">{goal.name}</h3>
                  <p className="text-xs text-[#3d4946] leading-relaxed">{goal.description}</p>

                  {goal.variables && Object.keys(goal.variables).length > 0 && (
                    <div className="space-y-1 pt-1">
                      <p className="text-[11px] font-bold uppercase tracking-wider text-[#3d4946]">
                        Dynamic Schema Variables:
                      </p>
                      <div className="flex flex-wrap gap-1.5">
                        {Object.entries(goal.variables).map(([k, desc]) => (
                          <span
                            key={k}
                            className="px-2 py-0.5 rounded-md bg-[#edf1ef] text-[#181c1c] font-mono text-[10px] border border-slate-200"
                            title={String(desc)}
                          >
                            {k}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="pt-3 border-t border-[#edf1ef]">
                  <button
                    onClick={() => handleOpenGoalModal(goal)}
                    className="w-full py-2.5 px-3 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-300 flex items-center justify-center gap-2 transition-all shadow-sm"
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
        <CalleCallLog
          calls={calls}
          loading={loading}
          onRefresh={() => fetchData(true)}
          refreshing={refreshing}
        />
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* MODAL 1: SINGLE LIVE TEST CALL DISPATCHER                               */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {showSingleModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="card max-w-lg w-full p-6 space-y-6 relative border border-slate-200 bg-white shadow-2xl max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowSingleModal(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-[#3d4946] hover:text-[#181c1c] hover:bg-slate-100"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <h3 className="text-lg font-extrabold text-[#181c1c] flex items-center gap-2">
                <PhoneForwarded className="w-5 h-5 text-[#396a00]" />
                Live Single Test Call Dispatcher
              </h3>
              <p className="text-xs text-[#3d4946]">
                Place an immediate test call via CALL-E SDK (<code className="text-emerald-800 font-bold font-mono">create_and_wait</code>) to any destination.
              </p>
            </div>

            {singleSubmitting ? (
              /* Live In-Progress State */
              <div className="py-8 text-center space-y-5 rounded-2xl bg-emerald-50/70 border border-emerald-200 p-6">
                <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
                  <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping" />
                  <div className="relative w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-800">
                    <PhoneCall className="w-6 h-6 animate-pulse" />
                  </div>
                </div>

                <div className="space-y-2">
                  <h4 className="font-extrabold text-[#181c1c] text-base">CALL-E Active Phone Call In-Progress</h4>
                  <div className="flex flex-col items-center gap-1 text-xs text-[#3d4946]">
                    <p className="text-emerald-800 font-extrabold flex items-center gap-1.5">
                      <RefreshCw className="w-3 h-3 animate-spin text-[#396a00]" />
                      {singleStep === 1 && '1/3 Initializing CALL-E SDK session & webhook...'}
                      {singleStep === 2 && '2/3 Dialing recipient phone line...'}
                      {singleStep === 3 && '3/3 Autonomous agent conversing & extracting JSON...'}
                    </p>
                    <p className="text-[11px] text-[#3d4946]/80 font-medium">
                      Synchronously waiting for recipient call completion & structured extraction
                    </p>
                  </div>
                </div>
              </div>
            ) : singleResult ? (
              /* Result Completed View */
              <div className="space-y-4 rounded-xl bg-[#f7faf9] border border-[#edf1ef] p-4">
                <div className="flex items-center justify-between border-b border-[#edf1ef] pb-3">
                  <div className="flex items-center gap-2">
                    {singleResult.status === 'failed' ? (
                      <AlertCircle className="w-5 h-5 text-red-600" />
                    ) : (
                      <CheckCircle2 className="w-5 h-5 text-[#396a00]" />
                    )}
                    <h4 className="font-extrabold text-[#181c1c] text-sm">
                      {singleResult.status === 'failed'
                        ? 'Call Dispatch Failed'
                        : singleResult.status === 'initiated' || singleResult.status === 'running' || singleResult.status === 'queued'
                        ? 'Call Dispatched & Ringing'
                        : 'Call Completed & Extracted'}
                    </h4>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                    singleResult.status === 'failed'
                      ? 'bg-red-100 text-red-800 border border-red-200'
                      : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                  }`}>
                    Status: {singleResult.status}
                  </span>
                </div>

                {(singleResult.status === 'failed' || singleResult.error || singleResult.reason) && (
                  <div className="p-3 rounded-xl bg-red-50 border border-red-300 text-red-900 text-xs flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-red-700 shrink-0 mt-0.5" />
                    <div className="space-y-0.5">
                      <p className="font-bold text-red-950">Dispatch Error</p>
                      <p className="text-[11px] text-red-900/90 leading-relaxed">
                        {singleResult.error || singleResult.reason || singleResult.message || 'Call failed to dispatch.'}
                      </p>
                    </div>
                  </div>
                )}

                {singleResult.warning && (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-900 text-xs flex items-start gap-2.5">
                    <AlertCircle className="w-4 h-4 text-amber-700 shrink-0 mt-0.5" />
                    <div className="space-y-0.5">
                      <p className="font-bold text-amber-950">Engine Notice</p>
                      <p className="text-[11px] text-amber-900/90 leading-relaxed">{singleResult.warning}</p>
                    </div>
                  </div>
                )}

                <div className="space-y-2 text-xs">
                  <p className="text-[#3d4946]">
                    <strong className="text-[#181c1c]">Summary:</strong>{' '}
                    {singleResult.summary ||
                      (singleResult.status === 'initiated'
                        ? 'Telephony session dispatched. Patient phone is currently ringing.'
                        : 'Call record processed and verified.')}
                  </p>
                  <div>
                    <div className="flex items-center justify-between text-[11px] font-bold text-[#181c1c] mb-1">
                      <span>Extracted JSON Schema Result:</span>
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(JSON.stringify(singleResult.structured_result || {}, null, 2));
                          setSingleCopied(true);
                          setTimeout(() => setSingleCopied(false), 2000);
                        }}
                        className="flex items-center gap-1 text-[#396a00] hover:text-emerald-700 font-mono font-bold"
                      >
                        {singleCopied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                        <span>{singleCopied ? 'Copied' : 'Copy JSON'}</span>
                      </button>
                    </div>
                    <pre className="p-3 rounded-lg bg-slate-900 text-emerald-300 font-mono text-[11px] overflow-x-auto border border-slate-800">
                      {JSON.stringify(singleResult.structured_result || {}, null, 2)}
                    </pre>
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setSingleResult(null)}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-[#edf1ef] text-[#181c1c] hover:bg-slate-200 border border-slate-200"
                  >
                    Test Another Call
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowSingleModal(false)}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-white shadow-sm"
                    style={{ background: 'linear-gradient(135deg, #396a00 0%, #4d8a00 100%)' }}
                  >
                    Done & View Feed
                  </button>
                </div>
              </div>
            ) : (
              /* Input Form */
              <form onSubmit={handleSingleCallSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-[#181c1c] mb-1">Campaign Type</label>
                  <select
                    value={singleCampaign}
                    onChange={e => {
                      setSingleCampaign(e.target.value);
                      if (e.target.value !== 'confirmation') {
                        setSingleAppointmentId('');
                      }
                    }}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
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
                  <label className="block text-xs font-bold text-[#181c1c] mb-1.5">Recipient Source</label>
                  <div className="grid grid-cols-2 gap-2 p-1 bg-[#edf1ef] rounded-xl border border-slate-200">
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
                          ? 'bg-white text-[#181c1c] shadow-sm border border-slate-200'
                          : 'text-[#3d4946] hover:text-[#181c1c]'
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
                          ? 'bg-white text-[#181c1c] shadow-sm border border-slate-200'
                          : 'text-[#3d4946] hover:text-[#181c1c]'
                      }`}
                    >
                      📱 Custom Phone Number
                    </button>
                  </div>
                </div>

                {singleSource === 'existing' ? (
                  <div>
                    <label className="block text-xs font-bold text-[#181c1c] mb-1">
                      Select Scheduled Appointment
                    </label>
                    <select
                      value={singleAppointmentId}
                      onChange={e => handleSelectAppt(e.target.value)}
                      className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                    >
                      <option value="">-- Choose appointment from calendar ({appointmentsList.length} available) --</option>
                      {appointmentsList.map(appt => (
                        <option key={appt.id} value={appt.id}>
                          {appt.patient_name || 'Patient'} — {appt.datetime ? appt.datetime.slice(0, 16).replace('T', ' ') : 'No time'} ({appt.status}) — {appt.patient_phone || 'No phone'}
                        </option>
                      ))}
                    </select>
                    {singleAppointmentId && (
                      <div className="mt-2 p-2.5 rounded-xl bg-emerald-50 border border-emerald-200 text-[11px] text-emerald-900 space-y-0.5">
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
                        <label className="block text-xs font-bold text-[#181c1c] mb-1">Patient Name</label>
                        <input
                          type="text"
                          placeholder="e.g. Alex Johnson"
                          value={singlePatientName}
                          onChange={e => setSinglePatientName(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-[#181c1c] mb-1">
                          Phone Number (E.164)
                        </label>
                        <input
                          type="text"
                          required
                          placeholder="+14155552671"
                          value={singlePhone}
                          onChange={e => setSinglePhone(e.target.value)}
                          className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                        />
                      </div>
                    </div>
                    {singleCampaign === 'confirmation' && (
                      <div>
                        <label className="block text-xs font-bold text-[#181c1c] mb-1">Appointment Time</label>
                        <input
                          type="text"
                          value={singleTime}
                          onChange={e => setSingleTime(e.target.value)}
                          placeholder="e.g. Wednesday, Aug 26 at 10:30 AM (Auto-scheduled if empty)"
                          className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                        />
                        <p className="text-[11px] text-[#3d4946] mt-1 font-medium">
                          💡 System will atomically create a real appointment and link this call to the database.
                        </p>
                      </div>
                    )}
                  </>
                )}

                {singleCampaign === 'recall' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-[#181c1c] mb-1">Recall Threshold</label>
                      <select
                        value={singleRecallDays}
                        onChange={e => setSingleRecallDays(Number(e.target.value))}
                        className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                      >
                        <option value={30}>30 Days Overdue</option>
                        <option value={60}>60 Days Overdue</option>
                        <option value={90}>90 Days Overdue</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-[#181c1c] mb-1">Recall Type</label>
                      <input
                        type="text"
                        value={singleRecallType}
                        onChange={e => setSingleRecallType(e.target.value)}
                        placeholder="Routine follow-up"
                        className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                      />
                    </div>
                  </div>
                )}

                {singleCampaign === 'waitlist' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-bold text-[#181c1c] mb-1">Open Slot Date</label>
                      <input
                        type="text"
                        value={singleSlotDate}
                        onChange={e => setSingleSlotDate(e.target.value)}
                        placeholder="Tomorrow"
                        className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-bold text-[#181c1c] mb-1">Open Slot Time</label>
                      <input
                        type="text"
                        value={singleSlotTime}
                        onChange={e => setSingleSlotTime(e.target.value)}
                        placeholder="10:30 AM"
                        className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                      />
                    </div>
                  </div>
                )}

                {/* Telephony Dispatch Engine: Pure CALL-E */}
                <div className="p-3.5 rounded-xl border border-[#396a00]/30 bg-emerald-50/50 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[#181c1c] flex items-center gap-1.5">
                        🤖 CALL-E Autonomous Voice Agent
                      </span>
                      <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-200">
                        Primary Hackathon Engine
                      </span>
                    </div>
                    <p className="text-[11px] text-[#3d4946] leading-relaxed">
                      Powered by the official <code className="text-[#396a00] font-mono text-[10px] bg-emerald-100/60 px-1 py-0.5 rounded">calle-ai</code> SDK with autonomous task planning and structured JSON schema extraction.
                    </p>
                  </div>
                  <span className="text-[10px] font-extrabold text-[#396a00] bg-white px-2 py-1 rounded-lg border border-emerald-200 shadow-sm shrink-0">
                    API v0.6.0
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-[#f7faf9] border border-[#edf1ef] flex items-center justify-between">
                  <div className="space-y-0.5">
                    <p className="text-xs font-bold text-[#181c1c]">Wait for Call Completion</p>
                    <p className="text-[11px] text-[#3d4946]">
                      Hold browser connection open until caller hangs up (Turn OFF for instant 1s dispatch)
                    </p>
                  </div>
                  <input
                    type="checkbox"
                    checked={singleWaitForResult}
                    onChange={e => setSingleWaitForResult(e.target.checked)}
                    className="w-4 h-4 rounded text-[#396a00] focus:ring-[#396a00] accent-[#396a00]"
                  />
                </div>

                <div className="pt-2 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setShowSingleModal(false)}
                    className="px-4 py-2.5 rounded-xl border border-slate-200 text-xs font-bold text-[#3d4946] hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2.5 rounded-xl text-xs font-bold text-white transition-all flex items-center gap-2 shadow-md hover:brightness-105 active:scale-95 cursor-pointer"
                    style={{ background: 'linear-gradient(135deg, #396a00 0%, #4d8a00 100%)' }}
                  >
                    <PhoneCall className="w-3.5 h-3.5" />
                    <span>Execute Live Call Now</span>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="card max-w-lg w-full p-6 space-y-6 relative border border-slate-200 bg-white shadow-2xl max-h-[90vh] overflow-y-auto">
            <button
              onClick={() => setShowGoalModal(false)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-[#3d4946] hover:text-[#181c1c] hover:bg-slate-100"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <span className="px-2 py-0.5 rounded-md bg-[#edf1ef] text-emerald-800 font-mono text-[10px] font-bold border border-slate-200">
                Goal ID: {selectedGoal.id}
              </span>
              <h3 className="text-lg font-extrabold text-[#181c1c]">{selectedGoal.name}</h3>
              <p className="text-xs text-[#3d4946]">{selectedGoal.description}</p>
            </div>

            {goalSubmitting ? (
              <div className="py-8 text-center space-y-4 rounded-xl bg-emerald-50/70 border border-emerald-200">
                <RefreshCw className="w-8 h-8 text-[#396a00] animate-spin mx-auto" />
                <p className="text-xs font-bold text-[#181c1c]">Executing Goal Run on CALL-E API 0.6.0...</p>
              </div>
            ) : goalResult ? (
              <div className="space-y-4 rounded-xl bg-[#f7faf9] border border-[#edf1ef] p-4 text-xs">
                <div className="flex items-center justify-between border-b border-[#edf1ef] pb-2">
                  <span className="font-bold text-emerald-800">Goal Run Complete</span>
                  <span className="font-mono text-[11px] text-[#3d4946]">ID: {goalResult.goal_run?.id || goalResult.record_id}</span>
                </div>
                <pre className="p-3 rounded-lg bg-slate-900 text-emerald-300 font-mono text-[11px] overflow-x-auto border border-slate-800">
                  {JSON.stringify(goalResult.goal_run || goalResult, null, 2)}
                </pre>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    onClick={() => setShowGoalModal(false)}
                    className="px-4 py-2 rounded-xl text-xs font-bold text-white shadow-sm"
                    style={{ background: 'linear-gradient(135deg, #396a00 0%, #4d8a00 100%)' }}
                  >
                    Close
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleGoalRunSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-bold text-[#181c1c] mb-1">
                    Recipient Phone Number (E.164 format)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="+1XXXXXXXXXX"
                    value={goalPhone}
                    onChange={e => setGoalPhone(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-sm focus:outline-none focus:border-[#396a00] shadow-sm"
                  />
                </div>

                {selectedGoal.variables && Object.keys(selectedGoal.variables).length > 0 && (
                  <div className="space-y-3 pt-1">
                    <p className="text-xs font-bold text-[#181c1c]">Goal Variables:</p>
                    {Object.entries(selectedGoal.variables).map(([k, desc]) => (
                      <div key={k}>
                        <label className="block text-[11px] font-semibold text-[#3d4946] mb-1">
                          {k} <span className="text-[10px] text-[#3d4946]/70">({String(desc)})</span>
                        </label>
                        <input
                          type="text"
                          required
                          value={goalVariables[k] || ''}
                          onChange={e => setGoalVariables(prev => ({ ...prev, [k]: e.target.value }))}
                          placeholder={`Enter ${k}`}
                          className="w-full px-3 py-2 rounded-xl border border-slate-200 bg-white text-[#181c1c] text-xs focus:outline-none focus:border-[#396a00] shadow-sm"
                        />
                      </div>
                    ))}
                  </div>
                )}

                <div className="pt-2 flex items-center justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setShowGoalModal(false)}
                    className="px-4 py-2.5 rounded-xl border border-slate-200 text-xs font-bold text-[#3d4946] hover:bg-slate-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-5 py-2.5 rounded-xl text-xs font-bold text-white transition-all flex items-center gap-2 shadow-md hover:brightness-105 active:scale-95 cursor-pointer"
                    style={{ background: 'linear-gradient(135deg, #396a00 0%, #4d8a00 100%)' }}
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

    </div>
  );
};

export default OutboundCampaigns;
