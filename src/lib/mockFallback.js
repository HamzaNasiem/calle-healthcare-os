/**
 * Resilient Offline/Demo Data Fallback Reference for Bytelytic Clinic OS (CALL-E Voice Platform)
 * 
 * ────────────────────────────────────────────────────────────────────────────────
 * ARCHITECTURAL NOTICE — DORMANT FALLBACK FIXTURE / NO ACTIVE INTERCEPTION:
 * 
 * This file contains offline reference schemas, test fixtures, and mock dataset
 * definitions used exclusively as a static fallback reference or offline preview.
 * 
 * 1. NO ACTIVE AXIOS/FETCH INTERCEPTOR:
 *    This module does NOT register any active interceptors with Axios or monkey-patch
 *    the browser's window.fetch.
 * 
 * 2. LIVE PRODUCTION & DEVELOPMENT CALLS:
 *    All active API requests (authentication, CALL-E autonomous campaigns, WebRTC
 *    sessions, prior authorization flows, and EHR updates) are dispatched directly
 *    through `src/lib/api.js` to the live backend server.
 * 
 * 3. FALLBACK SAFETY GUARANTEE:
 *    The `handleMockRoute` function below is a dormant, reference-only mock router.
 *    It is never called during normal online operation, ensuring zero unintended
 *    interception of active network traffic.
 * ────────────────────────────────────────────────────────────────────────────────
 */

export const MOCK_CLINIC = {
  id: "d3b07384-d113-46a6-a719-38cf89235d54",
  name: "Oakridge Physical Therapy & Wellness",
  owner_email: "owner@sunrisehealth.com",
  specialty: "Physical Therapy & Sports Rehab",
  city: "Chicago",
  timezone: "America/Chicago",
  primary_doctor_name: "Dr. Alexander Sunrise, MD",
  primary_doctor_credentials: "MD, Board Certified Sports Medicine",
  is_active: true,
  plan: "pro",
};

export const MOCK_PATIENTS = [
  { id: "pat-001", name: "Hamza Nasiem", phone: "+14155552671", email: "hamza@example.com", insurance_provider: "Blue Cross Blue Shield", insurance_member_id: "BCBS-98214", total_visits: 17, last_visit_date: "2026-08-28", recall_opted_out: false },
  { id: "pat-002", name: "Sarah Johnson", phone: "+14155550100", email: "sarah@example.com", insurance_provider: "Aetna", insurance_member_id: "AET-33491", total_visits: 8, last_visit_date: "2026-08-15", recall_opted_out: false },
  { id: "pat-003", name: "Michael Davis", phone: "+14155550101", email: "michael@example.com", insurance_provider: "UnitedHealthcare", insurance_member_id: "UHC-11928", total_visits: 12, last_visit_date: "2026-08-10", recall_opted_out: false },
  { id: "pat-004", name: "Emily Rodriguez", phone: "+14155550102", email: "emily@example.com", insurance_provider: "Cigna", insurance_member_id: "CIG-44910", total_visits: 4, last_visit_date: "2026-08-20", recall_opted_out: false },
  { id: "pat-005", name: "David Thompson", phone: "+14155550103", email: "david@example.com", insurance_provider: "Humana", insurance_member_id: "HUM-55912", total_visits: 6, last_visit_date: "2026-07-28", recall_opted_out: false },
  { id: "pat-006", name: "Jennifer Martinez", phone: "+14155550104", email: "jennifer@example.com", insurance_provider: "Blue Cross Blue Shield", insurance_member_id: "BCBS-66712", total_visits: 15, last_visit_date: "2026-08-22", recall_opted_out: false },
];

export const MOCK_APPOINTMENTS = [
  { id: "apt-101", patient_id: "pat-001", patient_name: "Hamza Nasiem", patient_phone: "+14155552671", appointment_type: "Physical Therapy Evaluation", datetime: new Date(Date.now() + 3600000).toISOString(), duration_minutes: 45, status: "confirmed", booked_by: "ai", reminder_sent: true, insurance_verified: true, notes: "Confirmed attendance via autonomous CALL-E 24h confirmation voice call." },
  { id: "apt-102", patient_id: "pat-002", patient_name: "Sarah Johnson", patient_phone: "+14155550100", appointment_type: "Follow-up Consultation", datetime: new Date(Date.now() + 7200000).toISOString(), duration_minutes: 30, status: "scheduled", booked_by: "staff", reminder_sent: false, insurance_verified: true, notes: "Post-surgery knee rehab follow-up." },
  { id: "apt-103", patient_id: "pat-003", patient_name: "Michael Davis", patient_phone: "+14155550101", appointment_type: "Sports Rehab Session", datetime: new Date(Date.now() + 10800000).toISOString(), duration_minutes: 60, status: "confirmed", booked_by: "ai", reminder_sent: true, insurance_verified: true, notes: "Patient confirmed attendance for afternoon evaluation." },
  { id: "apt-104", patient_id: "pat-004", patient_name: "Emily Rodriguez", patient_phone: "+14155550102", appointment_type: "Pain Management", datetime: new Date(Date.now() + 86400000).toISOString(), duration_minutes: 45, status: "scheduled", booked_by: "ai", reminder_sent: false, insurance_verified: true, notes: "Lower back pain intake evaluation." },
  { id: "apt-105", patient_id: "pat-005", patient_name: "David Thompson", patient_phone: "+14155550103", appointment_type: "Post-Surgery Recovery", datetime: new Date(Date.now() - 86400000).toISOString(), duration_minutes: 45, status: "completed", booked_by: "ai", reminder_sent: true, insurance_verified: true, notes: "Patient completed routine session." },
  { id: "apt-106", patient_id: "pat-006", patient_name: "Jennifer Martinez", patient_phone: "+14155550104", appointment_type: "Annual Wellness Check", datetime: new Date(Date.now() - 172800000).toISOString(), duration_minutes: 30, status: "no_show", booked_by: "staff", reminder_sent: true, insurance_verified: true, notes: "Missed scheduled appointment. CALL-E 2h recovery call triggered." },
];

export const MOCK_CALLS = [
  {
    id: "call-001",
    direction: "inbound",
    call_type: "booking",
    from_number: "+14155552671",
    to_number: "+18005551234",
    patient_name: "Hamza Nasiem",
    duration_seconds: 145,
    duration_formatted: "2m 25s",
    outcome: "booked",
    status: "ended",
    sentiment: "positive",
    sentiment_label: "Positive (0.96)",
    transcript: JSON.stringify([
      { speaker: "bot", text: "Hello! Thank you for calling Oakridge Physical Therapy. My name is CALL-E. How can I help you today?", timestamp: 0 },
      { speaker: "user", text: "Hi, I'd like to book an appointment with Dr. Alexander for Friday morning.", timestamp: 4 },
      { speaker: "bot", text: "I would be happy to schedule that! Dr. Alexander has an opening this Friday at 10:30 AM. Would that work for you?", timestamp: 9 },
      { speaker: "user", text: "Yes, Friday 10:30 AM is perfect.", timestamp: 14 },
      { speaker: "bot", text: "Great! I have booked you for Friday, 10:30 AM for a Physical Therapy Evaluation. You will receive an SMS confirmation shortly!", timestamp: 18 }
    ]),
    structured_result: { will_attend: "yes", booked_slot: "Friday 10:30 AM", confidence: 0.98 },
    created_at: new Date(Date.now() - 1800000).toISOString()
  },
  {
    id: "call-002",
    direction: "outbound",
    call_type: "confirmation",
    from_number: "Clinic AI",
    to_number: "+14155550100",
    patient_name: "Sarah Johnson",
    duration_seconds: 98,
    duration_formatted: "1m 38s",
    outcome: "confirmed",
    status: "completed",
    sentiment: "positive",
    sentiment_label: "Positive (0.94)",
    transcript: JSON.stringify([
      { speaker: "bot", text: "Hello Sarah, this is CALL-E from Oakridge Physical Therapy calling to confirm your appointment tomorrow at 2:00 PM.", timestamp: 0 },
      { speaker: "user", text: "Yes, I will be there! Thank you for the reminder.", timestamp: 5 },
      { speaker: "bot", text: "Wonderful! We look forward to seeing you tomorrow at 2:00 PM. Have a great day!", timestamp: 9 }
    ]),
    structured_result: { will_attend: "yes", cancellation_reason: null, confidence: 0.95 },
    created_at: new Date(Date.now() - 7200000).toISOString()
  }
];

export const MOCK_STATS = {
  calls: {
    total: 34,
    booked: 18,
    cancelled: 2,
    transferred: 3,
    faq_answered: 11,
    no_action: 0,
    vs_yesterday_pct: 14.5,
    inbound_handled: 22,
    inbound_total: 22,
    outbound_total: 12,
    outbound_confirmed: 10
  },
  appointments: {
    today: 6,
    today_confirmed: 4,
    today_pending: 2,
    tomorrow: 8,
    tomorrow_confirmed: 6,
    upcoming_7d: 28,
    monthly_total: 114
  },
  revenue: {
    today_protected: 900,
    saved_staff_hours: 18.5,
    roi_multiple: "8.4x",
    monthly_estimate: 17100
  },
  noshow_rate: {
    current: 4.8,
    industry_avg: 18.0,
    reduction_pct: 73.3
  }
};

export const MOCK_CALLE_STATUS = {
  configured: true,
  live_mode: true,
  mode: "live",
  api_version: "0.6.0",
  sdk_status: "connected",
  endpoint: "https://api.heycall-e.com"
};

export const MOCK_GOALS = [
  { id: "goal_conf_24h", name: "24-Hour Appointment Confirmation", campaign_type: "confirmation", status: "active", total_runs: 84, success_rate: 96.4 },
  { id: "goal_noshow_2h", name: "2-Hour Post-No-Show Recovery", campaign_type: "no_show", status: "active", total_runs: 22, success_rate: 81.8 },
  { id: "goal_recall_60d", name: "60-Day Patient Care Recall", campaign_type: "recall", status: "active", total_runs: 45, success_rate: 77.8 },
  { id: "goal_survey_nps", name: "Post-Visit Satisfaction NPS", campaign_type: "survey", status: "active", total_runs: 62, success_rate: 91.9 },
  { id: "goal_prior_auth", name: "Insurance Prior Auth Payor IVR", campaign_type: "prior_auth", status: "active", total_runs: 38, success_rate: 94.7 }
];

export const MOCK_PRIOR_AUTHS = [
  {
    id: "pa-991",
    patient_id: "pat-001",
    patient_name: "Hamza Nasiem",
    insurance_provider_name: "Blue Cross Blue Shield",
    insurance_prior_auth_phone: "1-800-676-2583",
    cpt_code: "99213",
    cpt_description: "Office/outpatient visit, established patient",
    icd10_code: "M54.5",
    urgency: "Standard",
    auth_status: "approved",
    call_status: "completed",
    authorization_number: "AUTH-882194-BCBS",
    reference_number: "REF-409122",
    representative_name: "Sarah Miller (Ext 402)",
    created_at: new Date(Date.now() - 3600000).toISOString()
  }
];

// Note: handleMockRoute has been completely removed to ensure zero route interception.
// All requests strictly execute live network calls to the backend API.
