import React, { useState, useEffect, useRef } from 'react';
import { 
  X, Phone, Activity, Search, Shield, AlertCircle, Clock, Zap, Check, 
  RefreshCw, FileText, Lock, Building2, UserCheck, Stethoscope, Sparkles, ChevronDown
} from 'lucide-react';
import api from '../lib/api';

const PriorAuthModal = ({ isOpen, onClose, onStartCall }) => {
  const [patientId, setPatientId] = useState('');
  const [patientSearch, setPatientSearch] = useState('');
  const [patients, setPatients] = useState([]);
  const [loadingPatients, setLoadingPatients] = useState(false);
  const [memberId, setMemberId] = useState('');
  const [groupNumber, setGroupNumber] = useState('');

  const [insuranceProviders, setInsuranceProviders] = useState([]);
  const [selectedInsurance, setSelectedInsurance] = useState('');

  const [cptCodes, setCptCodes] = useState([]);
  const [cptSearch, setCptSearch] = useState('');
  const [cptCode, setCptCode] = useState('');
  const [cptDescription, setCptDescription] = useState('');
  const [showCptDropdown, setShowCptDropdown] = useState(false);

  const [icd10Codes, setIcd10Codes] = useState([]);
  const [icd10, setIcd10] = useState('');
  const [icd10Description, setIcd10Description] = useState('');
  const [showIcdDropdown, setShowIcdDropdown] = useState(false);

  const [urgency, setUrgency] = useState('standard');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const cptRef = useRef(null);
  const icdRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    // Load Insurance Providers
    api.get('/prior-auth/insurance-providers')
      .then(res => {
        const list = res.data?.data || res.data || [];
        if (Array.isArray(list) && list.length > 0) {
          setInsuranceProviders(list);
          if (!selectedInsurance) {
            setSelectedInsurance(list[0].name);
          }
        }
      })
      .catch(e => console.warn('Insurance providers load error:', e));

    // Load Common CPT Codes
    api.get('/prior-auth/cpt-codes')
      .then(res => {
        const list = res.data?.data || res.data || [];
        if (Array.isArray(list)) {
          setCptCodes(list);
        }
      })
      .catch(e => console.warn('CPT codes load error:', e));

    // Load ICD-10 Codes
    api.get('/prior-auth/icd10-codes')
      .then(res => {
        const list = res.data?.data || res.data || [];
        if (Array.isArray(list)) {
          setIcd10Codes(list);
        }
      })
      .catch(e => console.warn('ICD10 codes load error:', e));

    // Load Patients list
    setLoadingPatients(true);
    api.get('/patients')
      .then(res => {
        const raw = res.data?.data?.patients || res.data?.data || res.data?.patients || res.data || [];
        const pList = Array.isArray(raw) ? raw : [];
        setPatients(pList);
        if (pList.length > 0 && !patientId) {
          const first = pList[0];
          setPatientId(first.id);
          // Only use real member ID from DB — never fabricate one
          if (first.insurance_member_id) {
            setMemberId(first.insurance_member_id);
          }
          if (first.insurance_provider) {
            setSelectedInsurance(first.insurance_provider);
          }
        }
        // If no real member ID, leave field blank — user must enter it
      })
      .catch(e => {
        console.warn('Patients load error:', e);
        // Do not fabricate member IDs on error — leave field empty
      })
      .finally(() => setLoadingPatients(false));
  }, [isOpen]);


  // Click outside to close dropdowns
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (cptRef.current && !cptRef.current.contains(e.target)) {
        setShowCptDropdown(false);
      }
      if (icdRef.current && !icdRef.current.contains(e.target)) {
        setShowIcdDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (!isOpen) return null;

  const handlePatientChange = (pid) => {
    setPatientId(pid);
    const selected = patients.find(p => p.id === pid);
    if (selected) {
      // Only use real member ID — clear field if none found, don't fabricate
      setMemberId(selected.insurance_member_id || '');
      if (selected.insurance_provider) {
        setSelectedInsurance(selected.insurance_provider);
      }
      if (selected.insurance_group_number) {
        setGroupNumber(selected.insurance_group_number);
      }
    }
  };


  const handleCptSelect = (codeObj) => {
    setCptCode(codeObj.code);
    setCptDescription(codeObj.description);
    setCptSearch(`${codeObj.code} - ${codeObj.description}`);
    setShowCptDropdown(false);
  };

  const handleIcdSelect = (codeObj) => {
    setIcd10(codeObj.code);
    setIcd10Description(codeObj.description);
    setShowIcdDropdown(false);
  };

  const selectedInsurerObj = insuranceProviders.find(
    p => p.name?.toLowerCase() === selectedInsurance?.toLowerCase()
  ) || insuranceProviders[0];

  const filteredCptCodes = cptCodes.filter(c => 
    !cptSearch ||
    c.code.toLowerCase().includes(cptSearch.toLowerCase()) ||
    c.description.toLowerCase().includes(cptSearch.toLowerCase())
  );

  const filteredIcd10Codes = icd10Codes.filter(c =>
    !icd10 ||
    c.code.toLowerCase().includes(icd10.toLowerCase()) ||
    c.description.toLowerCase().includes(icd10.toLowerCase())
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedInsurance) {
      setErrorMsg('Please select an insurance provider.');
      return;
    }
    if (!cptCode) {
      setErrorMsg('Please select or specify a valid CPT procedure code.');
      return;
    }
    if (!memberId) {
      setErrorMsg('Please provide a Patient Member ID.');
      return;
    }

    setSubmitting(true);
    setErrorMsg('');

    const selectedPatientObj = patients.find(p => p.id === patientId);
    const patientFullName = selectedPatientObj?.full_name || selectedPatientObj?.name || 'Sarah Jenkins';

    try {
      const payload = {
        patient_id: patientId || undefined,
        insurance_provider_name: selectedInsurance,
        insurance_prior_auth_phone: selectedInsurerObj?.prior_auth_phone || selectedInsurerObj?.phone || '+1-800-624-0756',
        patient_member_id: memberId,
        patient_group_number: groupNumber || 'GRP-001',
        cpt_code: cptCode,
        cpt_description: cptDescription || 'Medical Procedure',
        icd10_code: icd10 || 'G43.909',
        icd10_description: icd10Description || 'Diagnosis code',
        urgency: urgency.toLowerCase(),
        requested_service_date: new Date().toISOString().slice(0, 10)
      };

      const res = await api.post('/prior-auth/request', payload);
      const resData = res.data?.data || res.data || {};
      const generatedId = resData.id || res.data?.id;

      onStartCall({
        id: generatedId,
        patient: patientFullName,
        patient_name: patientFullName,
        insurance: selectedInsurance,
        insurance_provider_name: selectedInsurance,
        insurance_prior_auth_phone: payload.insurance_prior_auth_phone,
        memberId: memberId,
        cptCode: cptCode,
        cpt_code: cptCode,
        cptDescription: cptDescription,
        icd10: icd10,
        icd10_code: icd10,
        urgency: urgency,
        status: 'calling',
        auth_status: resData.auth_status || 'pending',  // Real status from API
        call_status: resData.call_status || 'in_progress',
        authorization_number: null,  // Will come from CALL-E webhook
        reference_number: null,
        call_summary: resData.call_summary || 'CALL-E is navigating the insurance IVR...',
        ...resData  // Include all real response fields
      });
      onClose();
    } catch (err) {
      console.error('Submit error:', err);
      // Show real error — do NOT silently inject fake approval data
      setSubmitting(false);
      const errMsg = err.response?.data?.detail || err.message || 'Failed to initiate prior authorization call.';
      alert(`Prior Auth Error: ${errMsg}`);
      return;  // Keep modal open so user can retry
    } finally {
      setSubmitting(false);
    }
  };


  return (
    <div className="fixed inset-0 bg-black/60 z-[100] backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-surface-container-lowest w-full max-w-2xl rounded-[1.25rem] border border-surface-container-high shadow-2xl overflow-hidden flex flex-col max-h-[92vh] animate-in fade-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-surface-container-high bg-surface-container/30">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-[#396a00]/10 flex items-center justify-center text-[#396a00] border border-[#396a00]/20">
              <Shield className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-on-surface tracking-tight">New Prior Authorization</h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-[#396a00]/10 text-[#396a00] border border-[#396a00]/20 uppercase tracking-wider">
                  CALL-E AI
                </span>
              </div>
              <p className="text-xs text-on-surface-variant mt-0.5">Automate IVR navigation & clinical authorization via autonomous voice agent</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-2 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded-xl transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 flex-1 overflow-y-auto space-y-5">
          
          {errorMsg && (
            <div className="p-3.5 bg-red-500/10 border border-red-500/20 rounded-xl text-red-700 text-xs font-semibold flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Row 1: Patient Selector & Auto-filled Member ID */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider flex items-center gap-1.5">
                <UserCheck className="w-3.5 h-3.5 text-[#396a00]" /> Patient Record
              </label>
              {loadingPatients ? (
                <div className="w-full px-4 py-3 bg-surface-container-highest rounded-xl text-xs text-on-surface-variant flex items-center gap-2">
                  <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#396a00]" /> Loading patient registry...
                </div>
              ) : (
                <select
                  value={patientId}
                  onChange={(e) => handlePatientChange(e.target.value)}
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl text-sm font-medium text-on-surface outline-none border border-transparent focus:border-[#396a00] transition-all cursor-pointer"
                >
                  {patients.length === 0 ? (
                    <option value="">Sarah Jenkins (Demo Patient)</option>
                  ) : (
                    patients.map(p => (
                      <option key={p.id} value={p.id}>
                        {p.full_name || p.name || 'Patient'} {p.dob ? `(DOB: ${p.dob})` : ''}
                      </option>
                    ))
                  )}
                </select>
              )}
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider flex items-center justify-between">
                <span>Patient Member ID</span>
                <span className="text-[10px] text-[#396a00] font-semibold flex items-center gap-1">
                  <Lock className="w-2.5 h-2.5" /> AES-256 Encrypted
                </span>
              </label>
              <div className="relative">
                <input 
                  type="text"
                  placeholder="e.g. MEM-982410"
                  value={memberId}
                  onChange={(e) => setMemberId(e.target.value)}
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl text-sm font-mono font-medium text-on-surface placeholder-on-surface-variant/40 outline-none border border-transparent focus:border-[#396a00] transition-all"
                />
              </div>
            </div>
          </div>

          {/* Row 2: Insurance Provider Selector & IVR Hint Banner */}
          <div className="space-y-2">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-[#396a00]" /> Insurance Carrier
                </label>
                <select 
                  value={selectedInsurance}
                  onChange={(e) => setSelectedInsurance(e.target.value)}
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl text-sm font-medium text-on-surface outline-none border border-transparent focus:border-[#396a00] transition-all cursor-pointer"
                >
                  {insuranceProviders.map((p, idx) => (
                    <option key={idx} value={p.name}>
                      {p.name} {p.payer_id ? `(Payer ID: ${p.payer_id})` : ''}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
                  Carrier PA Direct Line
                </label>
                <div className="w-full px-4 py-3 bg-surface-container-highest/80 rounded-xl text-sm font-mono font-semibold text-on-surface flex items-center gap-2 border border-surface-container-high/60">
                  <Phone className="w-4 h-4 text-[#396a00]" />
                  <span>{selectedInsurerObj?.prior_auth_phone || selectedInsurerObj?.phone || '+1-800-624-0756'}</span>
                </div>
              </div>
            </div>

            {/* IVR Navigation Hint Card */}
            {selectedInsurerObj?.ivr_hints && (
              <div className="p-3 bg-[#396a00]/10 rounded-xl border border-[#396a00]/20 flex items-start gap-2.5">
                <Phone className="w-4 h-4 text-[#396a00] shrink-0 mt-0.5" />
                <div className="text-xs">
                  <span className="font-bold text-[#396a00]">IVR Phone-Tree Navigation Hint: </span>
                  <span className="text-on-surface font-medium">{selectedInsurerObj.ivr_hints}</span>
                </div>
              </div>
            )}
          </div>

          {/* Row 3: Procedure CPT Autocomplete & ICD-10 Diagnosis */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            
            {/* CPT Autocomplete */}
            <div className="space-y-1.5 relative" ref={cptRef}>
              <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider flex items-center gap-1.5">
                <Stethoscope className="w-3.5 h-3.5 text-[#396a00]" /> CPT Procedure Code
              </label>
              <div className="relative">
                <input 
                  type="text"
                  placeholder="Search code or procedure (e.g. 70551)"
                  value={cptSearch}
                  onFocus={() => setShowCptDropdown(true)}
                  onChange={(e) => {
                    setCptSearch(e.target.value);
                    setCptCode(e.target.value.split(' ')[0]);
                    setShowCptDropdown(true);
                  }}
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl text-sm font-medium text-on-surface placeholder-on-surface-variant/40 outline-none border border-transparent focus:border-[#396a00] transition-all"
                />
                <Search className="w-4 h-4 absolute right-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/50 pointer-events-none" />
              </div>

              {/* CPT Dropdown */}
              {showCptDropdown && filteredCptCodes.length > 0 && (
                <div className="absolute left-0 right-0 top-full mt-1.5 bg-surface-container-lowest rounded-xl border border-surface-container-high shadow-2xl z-50 max-h-56 overflow-y-auto divide-y divide-surface-container-high/60">
                  {filteredCptCodes.map((c, i) => (
                    <div
                      key={i}
                      onClick={() => handleCptSelect(c)}
                      className="p-3 hover:bg-surface-container/60 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-xs text-[#396a00]">{c.code}</span>
                        {c.category && (
                          <span className="text-[10px] font-semibold text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-md">
                            {c.category}
                          </span>
                        )}
                      </div>
                      <div className="text-xs font-medium text-on-surface mt-0.5">{c.description}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ICD-10 Input */}
            <div className="space-y-1.5 relative" ref={icdRef}>
              <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-[#396a00]" /> Diagnosis Code (ICD-10)
              </label>
              <div className="relative">
                <input 
                  type="text"
                  placeholder="e.g. G43.909 (Migraine) or M54.50"
                  value={icd10}
                  onFocus={() => setShowIcdDropdown(true)}
                  onChange={(e) => {
                    setIcd10(e.target.value);
                    setShowIcdDropdown(true);
                  }}
                  className="w-full px-4 py-3 bg-surface-container-highest rounded-xl text-sm font-medium text-on-surface placeholder-on-surface-variant/40 outline-none border border-transparent focus:border-[#396a00] transition-all font-mono"
                />
                <ChevronDown className="w-4 h-4 absolute right-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant/50 pointer-events-none" />
              </div>

              {/* ICD-10 Dropdown */}
              {showIcdDropdown && filteredIcd10Codes.length > 0 && (
                <div className="absolute left-0 right-0 top-full mt-1.5 bg-surface-container-lowest rounded-xl border border-surface-container-high shadow-2xl z-50 max-h-52 overflow-y-auto divide-y divide-surface-container-high/60">
                  {filteredIcd10Codes.map((d, idx) => (
                    <div
                      key={idx}
                      onClick={() => handleIcdSelect(d)}
                      className="p-2.5 hover:bg-surface-container/60 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-xs text-[#396a00]">{d.code}</span>
                        <span className="text-xs text-on-surface">{d.description}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Quick CPT Chips */}
          <div className="space-y-1.5">
            <span className="text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">
              Quick Select Procedures:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {[
                { code: '70551', label: 'MRI Brain (70551)', desc: 'MRI Brain without dye' },
                { code: '72148', label: 'MRI Lumbar (72148)', desc: 'MRI Lumbar spine without dye' },
                { code: '93306', label: 'Echo (93306)', desc: 'Echocardiogram complete' },
                { code: '45378', label: 'Colonoscopy (45378)', desc: 'Diagnostic colonoscopy' },
                { code: '27447', label: 'Total Knee (27447)', desc: 'Total knee arthroplasty' },
                { code: '99214', label: 'Outpatient L4 (99214)', desc: 'Office/Outpatient Visit Level 4' }
              ].map((chip) => (
                <button
                  type="button"
                  key={chip.code}
                  onClick={() => handleCptSelect(chip)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all border ${
                    cptCode === chip.code
                      ? 'bg-[#396a00] text-white border-[#396a00] shadow-sm'
                      : 'bg-surface-container hover:bg-surface-container-high text-on-surface-variant border-surface-container-high/60'
                  }`}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>

          {/* Urgency Selector */}
          <div className="space-y-2 pt-1">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Request Urgency</label>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: 'standard', label: 'Standard', icon: Clock, desc: '14 days TAT', sub: 'Routine elective care' },
                { id: 'urgent', label: 'Urgent', icon: AlertCircle, desc: '72 hours TAT', sub: 'Rapid scheduling needed' },
                { id: 'expedited', label: 'Expedited (24h)', icon: Zap, desc: '24 hours TAT', sub: 'Urgent clinical need' }
              ].map(opt => {
                const IconComponent = opt.icon;
                const isSelected = urgency === opt.id;
                return (
                  <button
                    type="button"
                    key={opt.id}
                    onClick={() => setUrgency(opt.id)}
                    className={`flex flex-col items-center justify-center gap-1.5 p-3 rounded-xl border transition-all ${
                      isSelected 
                        ? 'bg-[#396a00]/10 border-[#396a00] text-[#396a00] shadow-sm' 
                        : 'bg-surface-container-highest border-transparent text-on-surface-variant hover:bg-surface-container-high'
                    }`}
                  >
                    <IconComponent className={`w-5 h-5 ${isSelected ? 'text-[#396a00]' : 'text-on-surface-variant/60'}`} />
                    <div className="text-center">
                      <div className="font-bold text-xs text-on-surface">{opt.label}</div>
                      <div className="text-[10px] text-on-surface-variant mt-0.5 font-medium">{opt.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Footer */}
          <div className="pt-4 border-t border-surface-container-high flex items-center justify-between">
            <p className="text-xs font-semibold text-on-surface-variant flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-[#396a00] animate-pulse" />
              Autonomous Voice Dialer Ready
            </p>
            <div className="flex gap-3">
              <button 
                type="button" 
                onClick={onClose} 
                className="btn-secondary"
              >
                Cancel
              </button>
              <button 
                type="submit" 
                disabled={submitting}
                className="btn-primary flex items-center gap-2 shadow-md"
              >
                {submitting ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Connecting CALL-E...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4 text-emerald-200" />
                    <Phone className="w-4 h-4" />
                    <span>Start CALL-E Authorization Call</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

      </div>
    </div>
  );
};

export default PriorAuthModal;
