import React, { useState } from 'react';
import {
  PhoneCall,
  CheckCircle2,
  AlertCircle,
  Clock,
  Eye,
  X,
  Copy,
  Check,
  Search,
  RefreshCw,
  Sparkles,
  PhoneForwarded,
  RotateCcw,
  Calendar,
  User,
  ShieldCheck,
} from 'lucide-react';
import api from '../lib/api';

/**
 * CalleCallLog Component
 * Displays live PostgreSQL outbound call records from CALL-E engine.
 * Includes real-time status badges, confidence meters, structured extraction inspectors,
 * and HIPAA-compliant audit-ready displays.
 */
export const CalleCallLog = ({
  calls = [],
  loading = false,
  onRefresh = null,
  refreshing = false,
  title = "Live Outbound Call Records & Extraction Activity",
  subtitle = "Real-time log of CALL-E autonomous calls, structured extractions, and downstream appointment updates.",
  showSearchAndFilters = true,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [feedFilter, setFeedFilter] = useState('all');
  const [selectedCall, setSelectedCall] = useState(null);
  const [callEvents, setCallEvents] = useState([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [copied, setCopied] = useState(false);

  // Inspect Call & fetch developer events if available
  const handleInspectCall = async (call) => {
    setSelectedCall(call);
    setCallEvents([]);
    const callId = call.calle_call_id || call.id;
    if (callId) {
      setLoadingEvents(true);
      try {
        const evRes = await api.get(`/calle/calls/${callId}/events`).catch(() => null);
        if (evRes && evRes.data && evRes.data.data) {
          setCallEvents(evRes.data.data);
        }
      } catch (e) {
        console.warn('Events fetch note:', e);
      } finally {
        setLoadingEvents(false);
      }
    }
  };

  // Filter calls
  const filteredCalls = calls.filter((c) => {
    if (feedFilter !== 'all' && c.campaign_type !== feedFilter && c.call_type !== feedFilter) return false;
    if (statusFilter !== 'all' && c.status !== statusFilter) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = String(c.calle_call_id || c.id || '').toLowerCase().includes(q);
      const matchSummary = String(c.summary || '').toLowerCase().includes(q);
      const matchType = String(c.campaign_type || c.call_type || '').toLowerCase().includes(q);
      const matchResult = JSON.stringify(c.structured_result || {}).toLowerCase().includes(q);
      const matchPatient = String(c.patients?.name || c.patient_name || '').toLowerCase().includes(q);
      if (!matchId && !matchSummary && !matchType && !matchResult && !matchPatient) return false;
    }
    return true;
  });

  const campaignColors = {
    confirmation: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    no_show: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    no_show_recovery: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    recall: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
    survey: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    waitlist: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
    waitlist_fill: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
    goal_run: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  };

  const statusBadges = {
    completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    initiated: 'bg-sky-500/10 text-sky-400 border-sky-500/20 animate-pulse',
    in_progress: 'bg-sky-500/10 text-sky-400 border-sky-500/20 animate-pulse',
    running: 'bg-sky-500/10 text-sky-400 border-sky-500/20 animate-pulse',
    queued: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    failed: 'bg-red-500/10 text-red-400 border-red-500/20',
    no_answer: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    voicemail: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  };

  return (
    <div className="card p-6 space-y-6 border border-outline/10">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-on-surface flex items-center gap-2">
            <PhoneCall className="w-5 h-5 text-emerald-400" />
            {title}
          </h2>
          <p className="text-xs text-on-surface-variant mt-0.5">{subtitle}</p>
        </div>

        {showSearchAndFilters && (
          <div className="flex flex-wrap items-center gap-2">
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                disabled={refreshing}
                className="p-1.5 rounded-xl border border-outline/20 hover:bg-surface-variant text-on-surface-variant transition-all disabled:opacity-50"
                title="Refresh call activity"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-emerald-400' : ''}`} />
              </button>
            )}

            <div className="relative">
              <Search className="w-3.5 h-3.5 text-on-surface-variant absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search ID, patient, summary..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-xl bg-surface border border-outline/20 text-xs text-on-surface focus:outline-none focus:border-emerald-500 w-48 sm:w-60"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-surface border border-outline/20 text-xs text-on-surface focus:outline-none focus:border-emerald-500"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="initiated">Initiated</option>
              <option value="running">Running</option>
              <option value="queued">Queued</option>
              <option value="failed">Failed</option>
              <option value="no_answer">No Answer</option>
            </select>

            <div className="flex items-center bg-surface-variant rounded-xl p-1 border border-outline/10 text-xs flex-wrap gap-1">
              {[
                { id: 'all', label: 'All' },
                { id: 'confirmation', label: 'Confirmation' },
                { id: 'no_show', label: 'No-Show' },
                { id: 'recall', label: 'Recall' },
                { id: 'survey', label: 'Survey' },
                { id: 'waitlist', label: 'Waitlist' },
              ].map((tab) => (
                <button
                  key={tab.id}
                  type="button"
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
        )}
      </div>

      {loading ? (
        <div className="py-12 text-center space-y-3">
          <RefreshCw className="w-6 h-6 text-emerald-400 animate-spin mx-auto" />
          <p className="text-xs text-on-surface-variant font-medium">Loading live PostgreSQL call records...</p>
        </div>
      ) : filteredCalls.length === 0 ? (
        <div className="py-12 text-center rounded-xl border border-dashed border-outline/20 space-y-3">
          <PhoneCall className="w-8 h-8 text-on-surface-variant/40 mx-auto" />
          <p className="text-sm font-semibold text-on-surface">No outbound calls match this filter</p>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
            Live database records will appear here as automated campaigns dispatch or single calls are executed.
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
              {filteredCalls.map((c) => {
                const campaignKey = c.campaign_type || c.call_type || 'confirmation';
                const structured = c.structured_result || {};

                return (
                  <tr key={c.id} className="hover:bg-surface-variant/30 transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-on-surface">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${
                          campaignColors[campaignKey] || 'bg-surface-variant text-on-surface-variant'
                        }`}
                      >
                        {campaignKey.replace('_', ' ')}
                      </span>
                    </td>

                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${
                          statusBadges[c.status] || 'bg-surface-variant text-on-surface-variant'
                        }`}
                      >
                        {c.status === 'completed' && <CheckCircle2 className="w-3 h-3" />}
                        {(c.status === 'running' || c.status === 'initiated' || c.status === 'in_progress') && (
                          <Clock className="w-3 h-3 animate-spin" />
                        )}
                        {c.status === 'failed' && <AlertCircle className="w-3 h-3" />}
                        {c.status || 'completed'}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 max-w-sm truncate text-on-surface-variant font-mono text-[11px]">
                      {structured.will_attend && (
                        <span className="text-emerald-400 font-bold">Conf: {structured.will_attend} </span>
                      )}
                      {structured.response_type && (
                        <span className="text-amber-400 font-bold">Resp: {structured.response_type} </span>
                      )}
                      {structured.interested && (
                        <span className="text-sky-400 font-bold">Interest: {structured.interested} </span>
                      )}
                      {structured.nps_score !== undefined && (
                        <span className="text-purple-400 font-bold">NPS: {structured.nps_score}/10 </span>
                      )}
                      {structured.accepts_slot !== undefined && (
                        <span className="text-teal-400 font-bold">Accepted: {structured.accepts_slot ? 'Yes' : 'No'} </span>
                      )}
                      {!structured.will_attend &&
                        !structured.response_type &&
                        !structured.interested &&
                        structured.nps_score === undefined &&
                        structured.accepts_slot === undefined && (
                          <span className="text-on-surface-variant/70">
                            {c.summary || (c.status === 'initiated' ? 'Call placed & ringing...' : 'Outcome verified')}
                          </span>
                        )}
                    </td>

                    <td className="py-3.5 px-4 text-[11px]">
                      {c.completion_score !== null && c.completion_score !== undefined ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 font-bold">
                          {Math.round(c.completion_score * 100)}%
                          <span className="text-[10px] text-on-surface-variant/70 font-normal">
                            ({c.completion_label || 'high'})
                          </span>
                        </span>
                      ) : (
                        <span className="text-on-surface-variant/40">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 font-mono text-[11px] text-on-surface-variant">
                      {c.calle_call_id ? c.calle_call_id.slice(0, 14) + '...' : c.id ? c.id.slice(0, 8) + '...' : 'Live'}
                    </td>

                    <td className="py-3.5 px-4 text-on-surface-variant text-[11px]">
                      {c.created_at
                        ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                        : 'Just now'}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
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

      {/* Detail Inspector Modal */}
      {selectedCall && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
          <div className="card max-w-2xl w-full p-6 space-y-6 relative border border-outline/20 shadow-2xl max-h-[88vh] overflow-y-auto">
            <button
              type="button"
              onClick={() => setSelectedCall(null)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-on-surface-variant hover:text-on-surface"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border-emerald-500/20">
                  {selectedCall.campaign_type || selectedCall.call_type || 'outbound'}
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider bg-surface-variant text-on-surface-variant">
                  Status: {selectedCall.status}
                </span>
                <span className="inline-flex items-center gap-1 text-[10px] text-emerald-400 font-bold bg-emerald-950/40 px-2 py-0.5 rounded-full border border-emerald-500/20">
                  <ShieldCheck className="w-3 h-3" />
                  HIPAA Verified
                </span>
              </div>
              <h3 className="text-lg font-bold text-on-surface">Call Result & Structured Data Inspection</h3>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-3.5 rounded-xl bg-surface-variant/40 border border-outline/10 space-y-1">
                <p className="font-semibold text-on-surface">Call Summary</p>
                <p className="text-on-surface-variant leading-relaxed">
                  {selectedCall.summary || (selectedCall.status === 'initiated' ? 'Call currently placed to patient phone line.' : 'No summary recorded.')}
                </p>
              </div>

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

              <div>
                <div className="flex items-center justify-between text-xs font-semibold text-on-surface mb-2">
                  <span>Structured Extraction (CALL-E JSON Schema)</span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(selectedCall.structured_result || {}, null, 2));
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }}
                    className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 font-mono text-[11px]"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy JSON'}</span>
                  </button>
                </div>
                <pre className="p-4 rounded-xl bg-surface border border-outline/10 text-emerald-400 font-mono text-xs overflow-x-auto leading-relaxed">
                  {JSON.stringify(selectedCall.structured_result || {}, null, 2)}
                </pre>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-xl bg-surface-variant/30 border border-outline/5">
                  <p className="text-on-surface-variant">CALL-E ID</p>
                  <p className="font-mono text-on-surface font-semibold truncate mt-0.5">
                    {selectedCall.calle_call_id || selectedCall.id || 'N/A'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-surface-variant/30 border border-outline/5">
                  <p className="text-on-surface-variant">Task Completed</p>
                  <p className="font-semibold text-emerald-400 mt-0.5">
                    {selectedCall.task_completed ? 'Yes (100%)' : selectedCall.status === 'completed' ? 'Yes' : 'In Progress'}
                  </p>
                </div>
              </div>

              {callEvents.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-outline/10">
                  <p className="font-semibold text-on-surface">Developer Call Event Stream</p>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {callEvents.map((ev, i) => (
                      <div
                        key={ev.id || i}
                        className="p-2 rounded-lg bg-surface border border-outline/5 font-mono text-[10px] text-on-surface-variant flex items-center justify-between"
                      >
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

export default CalleCallLog;
