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
  Volume2,
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
    confirmation: 'bg-emerald-100 text-emerald-800 border-emerald-300 font-bold',
    no_show: 'bg-amber-100 text-amber-900 border-amber-300 font-bold',
    no_show_recovery: 'bg-amber-100 text-amber-900 border-amber-300 font-bold',
    recall: 'bg-sky-100 text-sky-900 border-sky-300 font-bold',
    survey: 'bg-purple-100 text-purple-900 border-purple-300 font-bold',
    waitlist: 'bg-teal-100 text-teal-900 border-teal-300 font-bold',
    waitlist_fill: 'bg-teal-100 text-teal-900 border-teal-300 font-bold',
    goal_run: 'bg-blue-100 text-blue-900 border-blue-300 font-bold',
  };

  const statusBadges = {
    completed: 'bg-emerald-100 text-emerald-800 border-emerald-300 font-bold',
    initiated: 'bg-sky-100 text-sky-900 border-sky-300 font-bold animate-pulse',
    in_progress: 'bg-sky-100 text-sky-900 border-sky-300 font-bold animate-pulse',
    running: 'bg-sky-100 text-sky-900 border-sky-300 font-bold animate-pulse',
    queued: 'bg-amber-100 text-amber-900 border-amber-300 font-bold',
    failed: 'bg-red-100 text-red-800 border-red-300 font-bold',
    no_answer: 'bg-amber-100 text-amber-900 border-amber-300 font-bold',
    voicemail: 'bg-amber-100 text-amber-900 border-amber-300 font-bold',
  };

  return (
    <div className="card p-6 space-y-6 border border-[#edf1ef] bg-white shadow-card">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-bold text-[#181c1c] flex items-center gap-2">
            <PhoneCall className="w-5 h-5 text-[#396a00]" />
            {title}
          </h2>
          <p className="text-xs text-[#3d4946] mt-0.5">{subtitle}</p>
        </div>

        {showSearchAndFilters && (
          <div className="flex flex-wrap items-center gap-2">
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                disabled={refreshing}
                className="p-2 rounded-xl border border-slate-200 hover:bg-slate-50 text-[#3d4946] transition-all disabled:opacity-50"
                title="Refresh call activity"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-[#396a00]' : ''}`} />
              </button>
            )}

            <div className="relative">
              <Search className="w-3.5 h-3.5 text-[#3d4946] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search ID, patient, summary..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8 pr-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-[#181c1c] focus:outline-none focus:border-[#396a00] w-48 sm:w-60 shadow-sm"
              />
            </div>

            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-1.5 rounded-xl bg-white border border-slate-200 text-xs text-[#181c1c] font-medium focus:outline-none focus:border-[#396a00] shadow-sm"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="initiated">Initiated</option>
              <option value="running">Running</option>
              <option value="queued">Queued</option>
              <option value="failed">Failed</option>
              <option value="no_answer">No Answer</option>
            </select>

            <div className="flex items-center bg-[#edf1ef] rounded-xl p-1 border border-slate-200 text-xs flex-wrap gap-1">
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
                  className={`px-2.5 py-1 rounded-lg font-bold text-[11px] transition-all ${
                    feedFilter === tab.id
                      ? 'bg-white text-[#181c1c] shadow-sm border border-slate-200'
                      : 'text-[#3d4946] hover:text-[#181c1c]'
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
          <RefreshCw className="w-6 h-6 text-[#396a00] animate-spin mx-auto" />
          <p className="text-xs text-[#3d4946] font-medium">Loading live PostgreSQL call records...</p>
        </div>
      ) : filteredCalls.length === 0 ? (
        <div className="py-12 text-center rounded-xl border border-dashed border-slate-300 bg-[#f7faf9] space-y-3">
          <PhoneCall className="w-8 h-8 text-slate-400 mx-auto" />
          <p className="text-sm font-bold text-[#181c1c]">No outbound calls match this filter</p>
          <p className="text-xs text-[#3d4946] max-w-sm mx-auto">
            Live database records will appear here as automated campaigns dispatch or single calls are executed.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-[#edf1ef]">
          <table className="w-full text-left text-xs border-collapse bg-white">
            <thead>
              <tr className="border-b border-[#edf1ef] bg-[#f7faf9] text-[#3d4946] font-extrabold uppercase tracking-wider text-[11px]">
                <th className="py-3.5 px-4">Campaign</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4">Key Extracted Outcome</th>
                <th className="py-3.5 px-4">Confidence</th>
                <th className="py-3.5 px-4">Duration</th>
                <th className="py-3.5 px-4">CALL-E ID</th>
                <th className="py-3.5 px-4">Timestamp</th>
                <th className="py-3.5 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#edf1ef]">
              {filteredCalls.map((c) => {
                const campaignKey = c.campaign_type || c.call_type || 'confirmation';
                const structured = c.structured_result || {};

                return (
                  <tr key={c.id} className="hover:bg-[#f2f6f4] transition-colors">
                    <td className="py-3.5 px-4 font-semibold text-[#181c1c]">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${
                          campaignColors[campaignKey] || 'bg-slate-100 text-slate-800 border-slate-200'
                        }`}
                      >
                        {campaignKey.replace('_', ' ')}
                      </span>
                    </td>

                    <td className="py-3.5 px-4">
                      <span
                        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider ${
                          statusBadges[c.status] || 'bg-slate-100 text-slate-800 border-slate-200'
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

                    <td className="py-3.5 px-4 max-w-sm truncate text-[#181c1c] font-mono text-[11px]">
                      {structured.will_attend && (
                        <span className="text-emerald-800 font-extrabold bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                          Conf: {structured.will_attend}
                        </span>
                      )}
                      {structured.response_type && (
                        <span className="text-amber-900 font-extrabold bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
                          Resp: {structured.response_type}
                        </span>
                      )}
                      {structured.interested && (
                        <span className="text-sky-900 font-extrabold bg-sky-50 px-1.5 py-0.5 rounded border border-sky-200">
                          Interest: {structured.interested}
                        </span>
                      )}
                      {structured.nps_score !== undefined && (
                        <span className="text-purple-900 font-extrabold bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
                          NPS: {structured.nps_score}/10
                        </span>
                      )}
                      {structured.accepts_slot !== undefined && (
                        <span className="text-teal-900 font-extrabold bg-teal-50 px-1.5 py-0.5 rounded border border-teal-200">
                          Accepted: {structured.accepts_slot ? 'Yes' : 'No'}
                        </span>
                      )}
                      {!structured.will_attend &&
                        !structured.response_type &&
                        !structured.interested &&
                        structured.nps_score === undefined &&
                        structured.accepts_slot === undefined && (
                          <span className="text-[#3d4946]">
                            {c.summary || (c.status === 'initiated' ? 'Call placed & ringing...' : 'Outcome verified')}
                          </span>
                        )}
                    </td>

                    <td className="py-3.5 px-4 text-[11px]">
                      {c.completion_score !== null && c.completion_score !== undefined ? (
                        <span className="inline-flex items-center gap-1 text-emerald-800 font-extrabold">
                          {Math.round(c.completion_score * 100)}%
                          <span className="text-[10px] text-[#3d4946] font-medium">
                            ({c.completion_label || 'high'})
                          </span>
                        </span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 font-mono text-[11px] text-[#3d4946] font-medium">
                      {c.duration_seconds !== null && c.duration_seconds !== undefined ? (
                        <span>{Math.floor(c.duration_seconds / 60)}m {c.duration_seconds % 60}s</span>
                      ) : c.duration ? (
                        <span>{c.duration}s</span>
                      ) : (
                        <span className="text-slate-400">—</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 font-mono text-[11px] text-[#3d4946]">
                      {c.calle_call_id ? c.calle_call_id.slice(0, 14) + '...' : c.id ? c.id.slice(0, 8) + '...' : 'Live'}
                    </td>

                    <td className="py-3.5 px-4 text-[#3d4946] text-[11px] font-medium">
                      {c.created_at
                        ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                        : 'Just now'}
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleInspectCall(c)}
                        className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-[#3d4946] hover:text-[#181c1c] transition-all"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in">
          <div className="card max-w-2xl w-full p-6 space-y-6 relative border border-slate-200 bg-white shadow-2xl max-h-[88vh] overflow-y-auto">
            <button
              type="button"
              onClick={() => setSelectedCall(null)}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-[#3d4946] hover:text-[#181c1c] hover:bg-slate-100"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider bg-emerald-100 text-emerald-800 border-emerald-300">
                  {selectedCall.campaign_type || selectedCall.call_type || 'outbound'}
                </span>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase tracking-wider bg-slate-100 text-slate-800 border-slate-200">
                  Status: {selectedCall.status}
                </span>
                <span className="inline-flex items-center gap-1 text-[10px] text-emerald-800 font-bold bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                  <ShieldCheck className="w-3 h-3 text-[#396a00]" />
                  HIPAA Verified
                </span>
              </div>
              <h3 className="text-lg font-extrabold text-[#181c1c]">Call Result & Structured Data Inspection</h3>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-3.5 rounded-xl bg-[#f7faf9] border border-[#edf1ef] space-y-1">
                <p className="font-bold text-[#181c1c]">Call Summary</p>
                <p className="text-[#3d4946] leading-relaxed">
                  {selectedCall.summary || (selectedCall.status === 'initiated' ? 'Call currently placed to patient phone line.' : 'No summary recorded.')}
                </p>
              </div>

              {selectedCall.completion_score !== null && selectedCall.completion_score !== undefined && (
                <div className="p-3.5 rounded-xl bg-[#f7faf9] border border-[#edf1ef] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#181c1c]">CALL-E Confidence Score</span>
                    <span className="font-extrabold text-[#396a00]">
                      {Math.round(selectedCall.completion_score * 100)}% ({selectedCall.completion_label || 'high'})
                    </span>
                  </div>
                  <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
                    <div
                      className="bg-[#396a00] h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.round(selectedCall.completion_score * 100)}%` }}
                    />
                  </div>
                </div>
              )}

              <div>
                <div className="flex items-center justify-between text-xs font-bold text-[#181c1c] mb-2">
                  <span>Structured Extraction (CALL-E JSON Schema)</span>
                  <button
                    type="button"
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(selectedCall.structured_result || {}, null, 2));
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }}
                    className="flex items-center gap-1 text-[#396a00] hover:text-emerald-700 font-mono text-[11px] font-bold"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    <span>{copied ? 'Copied' : 'Copy JSON'}</span>
                  </button>
                </div>
                <pre className="p-4 rounded-xl bg-slate-900 text-emerald-300 font-mono text-xs overflow-x-auto leading-relaxed border border-slate-800">
                  {JSON.stringify(selectedCall.structured_result || {}, null, 2)}
                </pre>
              </div>

              {selectedCall.recording_url && (
                <div className="p-3.5 rounded-xl bg-[#f7faf9] border border-[#edf1ef] space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-[#181c1c] flex items-center gap-1.5">
                      <Volume2 className="w-3.5 h-3.5 text-[#396a00]" />
                      Authentic Call Audio Recording
                    </span>
                    <a
                      href={selectedCall.recording_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[11px] text-[#396a00] hover:underline font-bold"
                    >
                      Raw Audio Source ↗
                    </a>
                  </div>
                  <audio controls className="w-full h-8 rounded-lg" src={selectedCall.recording_url} />
                </div>
              )}

              <div className="grid grid-cols-3 gap-3">
                <div className="p-3 rounded-xl bg-[#f7faf9] border border-[#edf1ef]">
                  <p className="text-[#3d4946] text-[11px] font-medium">CALL-E ID</p>
                  <p className="font-mono text-[#181c1c] font-bold truncate mt-0.5" title={selectedCall.calle_call_id || selectedCall.id}>
                    {selectedCall.calle_call_id || selectedCall.id || 'N/A'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-[#f7faf9] border border-[#edf1ef]">
                  <p className="text-[#3d4946] text-[11px] font-medium">Duration</p>
                  <p className="font-bold text-emerald-800 mt-0.5">
                    {selectedCall.duration_seconds !== null && selectedCall.duration_seconds !== undefined
                      ? `${Math.floor(selectedCall.duration_seconds / 60)}m ${selectedCall.duration_seconds % 60}s`
                      : selectedCall.duration ? `${selectedCall.duration}s` : 'N/A'}
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-[#f7faf9] border border-[#edf1ef]">
                  <p className="text-[#3d4946] text-[11px] font-medium">Task Completed</p>
                  <p className="font-bold text-emerald-800 mt-0.5">
                    {selectedCall.task_completed ? 'Yes (100%)' : selectedCall.status === 'completed' ? 'Yes' : 'In Progress'}
                  </p>
                </div>
              </div>

              {callEvents.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-[#edf1ef]">
                  <p className="font-bold text-[#181c1c]">Developer Call Event Stream</p>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {callEvents.map((ev, i) => (
                      <div
                        key={ev.id || i}
                        className="p-2 rounded-lg bg-[#f7faf9] border border-[#edf1ef] font-mono text-[10px] text-[#3d4946] flex items-center justify-between"
                      >
                        <span className="text-[#396a00] font-bold">{ev.type}</span>
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
