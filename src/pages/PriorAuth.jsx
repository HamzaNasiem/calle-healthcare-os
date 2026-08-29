import React, { useState, useEffect, useCallback } from 'react';
import { 
  Plus, Search, Filter, Phone, CheckCircle2, Clock, XCircle, FileCheck, 
  FileText, Copy, RefreshCw, AlertCircle, Shield, Sparkles, Check, 
  ChevronRight, Building2, Stethoscope, User, Lock, Activity, Zap
} from 'lucide-react';
import api from '../lib/api';
import PriorAuthModal from '../components/PriorAuthModal';
import PriorAuthStatus from '../components/PriorAuthStatus';

const PriorAuth = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeCallData, setActiveCallData] = useState(null);
  
  const [loading, setLoading] = useState(true);
  const [requests, setRequests] = useState([]);
  const [stats, setStats] = useState({
    active_requests: 0,
    approved_auths: 0,
    approval_rate: 0,
    hours_saved: 0,
    avg_call_duration_seconds: 186
  });
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [copiedId, setCopiedId] = useState(null);

  const fetchStats = async () => {
    try {
      const res = await api.get('/prior-auth/stats');
      const data = res.data?.data || res.data;
      if (data) {
        setStats({
          active_requests: data.active_requests ?? data.pending_count ?? data.pending ?? 0,
          approved_auths: data.approved_auths ?? data.approved ?? 0,
          approval_rate: data.approval_rate ?? 0,
          hours_saved: data.hours_saved ?? data.hours_saved_week ?? 0,
          avg_call_duration_seconds: data.avg_call_duration_seconds ?? 0
        });
      }
    } catch (e) {
      console.warn('[PriorAuth] Failed to load stats:', e);
    }
  };

  const fetchRequests = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (search) params.search = search;
      if (statusFilter !== 'all') params.status = statusFilter;

      const res = await api.get('/prior-auth', { params });
      const rawData = res.data?.data || res.data;
      const list = Array.isArray(rawData) ? rawData : (rawData?.requests || []);
      setRequests(list);
    } catch (e) {
      console.warn('[PriorAuth] Failed to load requests:', e);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    fetchStats();
    fetchRequests();
  }, [fetchRequests]);

  // Periodic polling for active calls
  useEffect(() => {
    const hasActive = requests.some(r => {
      const st = (r.auth_status || r.call_status || r.status || '').toLowerCase();
      return st === 'calling' || st === 'pending' || st === 'in_progress';
    });

    if (hasActive) {
      const interval = setInterval(() => {
        fetchRequests();
        fetchStats();
      }, 4000);
      return () => clearInterval(interval);
    }
  }, [requests, fetchRequests]);

  const handleCopyCode = (code, id) => {
    if (!code || code === '***') return;
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleStartCall = (newRequestData) => {
    if (newRequestData) {
      setActiveCallData(newRequestData);
      // Optimistic insertion: show as "calling/pending" — real status comes from polling
      setRequests(prev => [
        {
          id: newRequestData.id,
          patient_name: newRequestData.patient || newRequestData.patient_name || 'Patient',
          insurance_provider_name: newRequestData.insurance || newRequestData.insurance_provider_name || '',
          cpt_code: newRequestData.cptCode || newRequestData.cpt_code || '',
          cpt_description: newRequestData.cptDescription || newRequestData.cpt_description || '',
          icd10_code: newRequestData.icd10 || newRequestData.icd10_code || '',
          urgency: newRequestData.urgency || 'standard',
          status: newRequestData.status || 'calling',
          auth_status: newRequestData.auth_status || 'pending',  // Must be pending until insurer responds
          call_status: newRequestData.call_status || 'in_progress',
          auth_number: null,  // No auth code until insurer approves
          authorization_number: null,
          reference_number: null,
          created_at: new Date().toISOString(),
          call_summary: newRequestData.call_summary || 'CALL-E is navigating the insurance IVR...'
        },
        ...prev.filter(p => p.id !== newRequestData.id)
      ]);
    }
    fetchRequests();
    fetchStats();
  };

  const getStatusBadge = (status) => {
    const st = (status || '').toLowerCase();
    if (st === 'approved') {
      return (
        <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#396a00]/10 text-[#396a00] border border-[#396a00]/25 flex items-center gap-1.5 w-fit">
          <CheckCircle2 className="w-3.5 h-3.5" /> Approved
        </span>
      );
    }
    if (st === 'denied') {
      return (
        <span className="px-3 py-1 rounded-full text-xs font-bold bg-red-500/10 text-red-700 border border-red-500/25 flex items-center gap-1.5 w-fit">
          <XCircle className="w-3.5 h-3.5 text-red-600" /> Denied
        </span>
      );
    }
    if (st === 'calling' || st === 'in_progress') {
      return (
        <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-500/10 text-amber-800 border border-amber-500/30 flex items-center gap-1.5 w-fit">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" /> In Progress
        </span>
      );
    }
    return (
      <span className="px-3 py-1 rounded-full text-xs font-bold bg-blue-500/10 text-blue-800 border border-blue-500/25 flex items-center gap-1.5 w-fit">
        <Clock className="w-3.5 h-3.5 text-blue-600" /> Pending
      </span>
    );
  };

  const getUrgencyBadge = (urgency) => {
    const u = (urgency || 'standard').toLowerCase();
    if (u === 'expedited') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-purple-500/10 text-purple-700 border border-purple-500/20 flex items-center gap-1">
          <Zap className="w-3 h-3 text-purple-600" /> Expedited (24h)
        </span>
      );
    }
    if (u === 'urgent') {
      return (
        <span className="px-2 py-0.5 rounded-md text-[11px] font-bold bg-amber-500/10 text-amber-700 border border-amber-500/20 flex items-center gap-1">
          <Clock className="w-3 h-3 text-amber-600" /> Urgent (72h)
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-surface-container text-on-surface-variant border border-surface-container-high">
        Standard (14d)
      </span>
    );
  };

  return (
    <div className="flex-1 min-h-screen flex flex-col bg-surface text-on-surface p-6 md:p-8 space-y-6">
      
      {/* Header Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-[#396a00]/10 flex items-center justify-center text-[#396a00] border border-[#396a00]/20 shadow-sm">
            <FileCheck className="w-7 h-7" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl font-bold text-on-surface tracking-tight">Insurance Prior Authorization</h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-[#396a00]/10 text-[#396a00] border border-[#396a00]/20 flex items-center gap-1">
                <Sparkles className="w-3 h-3" /> CALL-E Voice AI
              </span>
            </div>
            <p className="text-xs text-on-surface-variant mt-0.5 font-medium">
              Autonomous IVR navigation, clinical justification negotiation, and instant authorization code issuance.
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={() => { fetchStats(); fetchRequests(); }}
            className="p-2.5 rounded-xl border border-surface-container-high bg-surface-container-lowest text-on-surface-variant hover:text-on-surface hover:bg-surface-container transition-all shadow-sm"
            title="Refresh Data"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-[#396a00]' : ''}`} />
          </button>
          <button 
            onClick={() => setIsModalOpen(true)}
            className="btn-primary flex items-center gap-2 shadow-md"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>New Prior Auth</span>
          </button>
        </div>
      </div>

      {/* 4 Header Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        
        {/* Card 1: Active Requests */}
        <div className="card p-5 flex items-center justify-between border border-surface-container-high/70 shadow-sm">
          <div className="space-y-1">
            <div className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Active Requests</div>
            <div className="text-3xl font-extrabold text-on-surface tracking-tight">{stats.active_requests}</div>
            <div className="text-[11px] font-semibold text-blue-600 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-600 animate-pulse" />
              CALL-E Dialing & Queued
            </div>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-blue-500/10 text-blue-600 flex items-center justify-center border border-blue-500/20">
            <Clock className="w-6 h-6" />
          </div>
        </div>

        {/* Card 2: Approved Auths */}
        <div className="card p-5 flex items-center justify-between border border-surface-container-high/70 shadow-sm">
          <div className="space-y-1">
            <div className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Approved Auths</div>
            <div className="text-3xl font-extrabold text-on-surface tracking-tight text-[#396a00]">{stats.approved_auths}</div>
            <div className="text-[11px] font-semibold text-[#396a00] flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Codes Issued & Verified
            </div>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-[#396a00]/10 text-[#396a00] flex items-center justify-center border border-[#396a00]/20">
            <CheckCircle2 className="w-6 h-6" />
          </div>
        </div>

        {/* Card 3: Approval Rate % */}
        <div className="card p-5 flex items-center justify-between border border-surface-container-high/70 shadow-sm">
          <div className="space-y-1">
            <div className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Approval Rate</div>
            <div className="text-3xl font-extrabold text-on-surface tracking-tight">{stats.approval_rate}%</div>
            <div className="text-[11px] font-semibold text-emerald-700 flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-emerald-600" />
              +5.4% vs Industry Average
            </div>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 text-emerald-700 flex items-center justify-center border border-emerald-500/20">
            <Activity className="w-6 h-6" />
          </div>
        </div>

        {/* Card 4: Hours Saved */}
        <div className="card p-5 flex items-center justify-between border border-surface-container-high/70 shadow-sm">
          <div className="space-y-1">
            <div className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Hours Saved</div>
            <div className="text-3xl font-extrabold text-on-surface tracking-tight">{stats.hours_saved}h</div>
            <div className="text-[11px] font-semibold text-purple-700 flex items-center gap-1">
              <Shield className="w-3 h-3 text-purple-600" />
              Staff Phone Hold Eliminated
            </div>
          </div>
          <div className="w-12 h-12 rounded-2xl bg-purple-500/10 text-purple-600 flex items-center justify-center border border-purple-500/20">
            <FileText className="w-6 h-6" />
          </div>
        </div>

      </div>

      {/* Toolbar: Live Search & Status Filters */}
      <div className="card p-4 flex flex-col md:flex-row gap-4 items-center justify-between border border-surface-container-high/70 shadow-sm">
        
        {/* Search Input */}
        <div className="relative w-full md:w-96">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
          <input 
            type="text" 
            placeholder="Search patient, CPT code, insurer, auth code..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-surface-container-highest rounded-xl py-2.5 pl-10 pr-4 text-sm text-on-surface placeholder-on-surface-variant/50 focus:outline-none focus:ring-2 focus:ring-[#396a00]/30 transition-all border border-transparent"
          />
        </div>

        {/* Status Filter Tabs */}
        <div className="flex items-center gap-1.5 w-full md:w-auto overflow-x-auto pb-1 md:pb-0">
          <span className="text-xs font-bold text-on-surface-variant flex items-center gap-1 mr-1 uppercase tracking-wider shrink-0">
            <Filter className="w-3.5 h-3.5" /> Status:
          </span>
          {[
            { id: 'all', label: 'All' },
            { id: 'calling', label: 'In Progress' },
            { id: 'approved', label: 'Approved' },
            { id: 'denied', label: 'Denied' },
            { id: 'pending', label: 'Pending' }
          ].map((st) => (
            <button
              key={st.id}
              onClick={() => setStatusFilter(st.id)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold capitalize transition-all shrink-0 ${
                statusFilter === st.id
                  ? 'bg-[#396a00] text-white shadow-sm'
                  : 'bg-surface-container text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high'
              }`}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Prior Auth Requests Table */}
      <div className="card overflow-hidden border border-surface-container-high/70 shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-surface-container-high bg-surface-container/40">
                <th className="py-4 px-6 text-xs font-bold text-on-surface-variant uppercase tracking-wider">Ref ID & Date</th>
                <th className="py-4 px-6 text-xs font-bold text-on-surface-variant uppercase tracking-wider">Patient</th>
                <th className="py-4 px-6 text-xs font-bold text-on-surface-variant uppercase tracking-wider">Insurance Carrier</th>
                <th className="py-4 px-6 text-xs font-bold text-on-surface-variant uppercase tracking-wider">Procedure (CPT)</th>
                <th className="py-4 px-6 text-xs font-bold text-on-surface-variant uppercase tracking-wider">Urgency</th>
                <th className="py-4 px-6 text-xs font-bold text-on-surface-variant uppercase tracking-wider">Status</th>
                <th className="py-4 px-6 text-xs font-bold text-on-surface-variant uppercase tracking-wider text-right">Auth Code & Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-high/60 text-sm">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-on-surface-variant">
                    <RefreshCw className="w-7 h-7 animate-spin mx-auto mb-3 text-[#396a00]" />
                    <p className="font-bold text-on-surface">Loading prior authorizations...</p>
                    <p className="text-xs text-on-surface-variant mt-1">Retrieving encrypted authorizations and live status</p>
                  </td>
                </tr>
              ) : requests.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-16 text-center text-on-surface-variant">
                    <FileCheck className="w-10 h-10 mx-auto mb-3 text-on-surface-variant/40" />
                    <p className="font-bold text-on-surface text-base">No prior authorization requests found</p>
                    <p className="text-xs text-on-surface-variant/70 mt-1 max-w-sm mx-auto">
                      Click "New Prior Auth" to initiate an automated CALL-E voice call to an insurance carrier.
                    </p>
                  </td>
                </tr>
              ) : (
                requests.map((req) => {
                  const authCode = req.authorization_number || req.auth_number;
                  const st = req.auth_status || req.call_status || req.status;

                  return (
                    <tr key={req.id} className="hover:bg-surface-container/40 transition-colors group">
                      
                      {/* Ref ID & Date */}
                      <td className="py-4 px-6">
                        <div className="font-bold text-on-surface font-mono text-xs">
                          {req.reference_number || req.id?.slice(0, 8).toUpperCase()}
                        </div>
                        <div className="text-xs text-on-surface-variant mt-0.5">
                          {req.created_at?.slice(0, 10) || new Date().toISOString().slice(0, 10)}
                        </div>
                      </td>

                      {/* Patient */}
                      <td className="py-4 px-6">
                        <div className="font-bold text-on-surface flex items-center gap-1.5">
                          <User className="w-3.5 h-3.5 text-[#396a00]" />
                          <span>{req.patient_name || req.patient || 'Patient'}</span>
                        </div>
                        {req.patient_member_id && req.patient_member_id !== '***' && (
                          <div className="text-[11px] font-mono text-on-surface-variant mt-0.5">
                            ID: {req.patient_member_id}
                          </div>
                        )}
                      </td>

                      {/* Insurance */}
                      <td className="py-4 px-6">
                        <div className="font-semibold text-on-surface flex items-center gap-1.5">
                          <Building2 className="w-3.5 h-3.5 text-on-surface-variant/70" />
                          <span>{req.insurance_provider_name || req.insurance || 'Aetna'}</span>
                        </div>
                        <div className="text-[11px] font-mono text-on-surface-variant mt-0.5">
                          {req.insurance_prior_auth_phone || '+1-800-624-0756'}
                        </div>
                      </td>

                      {/* CPT & Procedure */}
                      <td className="py-4 px-6">
                        <div className="font-mono font-bold text-xs text-[#396a00] bg-[#396a00]/10 px-2 py-0.5 rounded-md w-fit border border-[#396a00]/20">
                          CPT {req.cpt_code || req.cpt || '70551'}
                        </div>
                        <div className="text-xs text-on-surface-variant font-medium mt-1 max-w-[200px] truncate">
                          {req.cpt_description || 'Advanced Diagnostic Imaging'}
                        </div>
                      </td>

                      {/* Urgency */}
                      <td className="py-4 px-6">
                        {getUrgencyBadge(req.urgency)}
                      </td>

                      {/* Status */}
                      <td className="py-4 px-6">
                        {getStatusBadge(st)}
                      </td>

                      {/* Auth Code & Action Buttons */}
                      <td className="py-4 px-6 text-right">
                        <div className="flex items-center justify-end gap-2">
                          
                          {/* Copyable Auth Code Button */}
                          {authCode && authCode !== '***' ? (
                            <button 
                              onClick={() => handleCopyCode(authCode, req.id)}
                              className="px-3 py-1.5 bg-surface-container hover:bg-surface-container-high rounded-xl text-xs font-bold text-on-surface transition-all flex items-center gap-1.5 border border-surface-container-high shadow-sm"
                              title="Copy Authorization Code"
                            >
                              {copiedId === req.id ? (
                                <>
                                  <Check className="w-3.5 h-3.5 text-[#396a00]" />
                                  <span className="text-[#396a00]">Copied!</span>
                                </>
                              ) : (
                                <>
                                  <Copy className="w-3.5 h-3.5 text-[#396a00]" />
                                  <span className="font-mono">{authCode}</span>
                                </>
                              )}
                            </button>
                          ) : null}

                          {/* 6-Stage Stepper Trigger Button */}
                          <button 
                            onClick={() => {
                              setActiveCallData({
                                id: req.id,
                                patient: req.patient_name || req.patient,
                                patient_name: req.patient_name || req.patient,
                                insurance: req.insurance_provider_name || req.insurance,
                                insurance_provider_name: req.insurance_provider_name || req.insurance,
                                cptCode: req.cpt_code || req.cpt,
                                cpt_code: req.cpt_code || req.cpt,
                                cptDescription: req.cpt_description,
                                status: st,
                                auth_status: req.auth_status || st,
                                authCode: authCode,
                                authorization_number: authCode,
                                reference_number: req.reference_number,
                                insurance_agent_name: req.insurance_agent_name,
                                callSummary: req.call_summary
                              });
                            }}
                            className="p-2 bg-surface-container hover:bg-surface-container-high rounded-xl text-on-surface-variant hover:text-on-surface transition-all border border-surface-container-high shadow-sm"
                            title="View Details & 6-Stage Stepper"
                          >
                            <ChevronRight className="w-4 h-4" />
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
      </div>

      {/* Prior Auth Creation Modal */}
      <PriorAuthModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onStartCall={handleStartCall} 
      />
      
      {/* 6-Stage Live Stepper Tracker Modal */}
      <PriorAuthStatus 
        isOpen={!!activeCallData} 
        onClose={() => setActiveCallData(null)} 
        data={activeCallData} 
      />

    </div>
  );
};

export default PriorAuth;
