-- ============================================================
-- Bytelytic Clinic OS — Full PostgreSQL Schema
-- Run this against your Supabase project (SQL Editor)
-- RULE: clinic_id on EVERY table — multi-tenant from day 1
-- ============================================================


-- ============================================================
-- TABLE 1: clinics
-- ============================================================
CREATE TABLE clinics (
  id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name                     TEXT        NOT NULL,
  owner_email              TEXT        UNIQUE NOT NULL,
  specialty                TEXT,
  city                     TEXT,
  primary_doctor_name      TEXT,
  primary_doctor_credentials TEXT,
  primary_doctor_phone     TEXT,
  npi_number               TEXT,
  medical_license          TEXT,
  phone_number             TEXT,                                         -- Twilio number assigned to clinic
  twilio_number            TEXT,                                         -- same as above, kept for clarity
  retell_agent_id          TEXT,                                         -- Retell AI agent ID for this clinic
  google_calendar_id       TEXT,                                         -- Google Calendar ID
  google_refresh_token     TEXT,                                         -- OAuth refresh token for calendar
  timezone                 TEXT        DEFAULT 'America/Chicago',
  business_hours           JSONB       DEFAULT '{"mon":"08:00-18:00","tue":"08:00-18:00","wed":"08:00-18:00","thu":"08:00-18:00","fri":"08:00-18:00"}',
  appointment_types        JSONB       DEFAULT '[{"name":"Initial Eval","duration":60},{"name":"Follow-up","duration":30}]',
  recall_days              INTEGER[]   DEFAULT '{30,60,90}',
  monthly_revenue_per_visit INTEGER   DEFAULT 150,
  is_active                BOOLEAN     DEFAULT true,
  created_at               TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- TABLE 2: patients
-- ============================================================
CREATE TABLE patients (
  id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id         UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  name              TEXT        NOT NULL,
  phone             TEXT        NOT NULL,
  email             TEXT,
  date_of_birth     DATE,
  insurance_provider TEXT,
  insurance_member_id TEXT,
  last_visit_date   DATE,
  total_visits      INTEGER     DEFAULT 0,
  no_show_count     INTEGER     DEFAULT 0,
  preferred_time    TEXT,                                                -- "morning", "afternoon", "evening"
  notes             TEXT,
  recall_opted_out  BOOLEAN     DEFAULT false,
  created_at        TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(clinic_id, phone)
);


-- ============================================================
-- TABLE 3: appointments
-- ============================================================
CREATE TABLE appointments (
  id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id           UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  patient_id          UUID        REFERENCES patients(id),
  patient_name        TEXT        NOT NULL,                              -- denormalized for speed
  patient_phone       TEXT        NOT NULL,
  appointment_type    TEXT        NOT NULL,
  datetime            TIMESTAMPTZ NOT NULL,
  duration_minutes    INTEGER     DEFAULT 30,
  google_event_id     TEXT,                                             -- Google Calendar event ID
  status              TEXT        DEFAULT 'scheduled'
    CHECK (status IN ('scheduled','confirmed','completed','cancelled','no_show')),
  confirmed_at        TIMESTAMPTZ,
  reminder_sent       BOOLEAN     DEFAULT false,
  insurance_verified  BOOLEAN     DEFAULT false,
  revenue_amount      INTEGER,                                          -- in USD cents
  booked_by           TEXT        DEFAULT 'ai'
    CHECK (booked_by IN ('ai','staff','patient')),
  notes               TEXT,
  noshow_risk         REAL,                                             -- AI generated risk score 0.0-1.0
  followup_sent       BOOLEAN     DEFAULT false,
  created_at          TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- TABLE 4: calls
-- ============================================================
CREATE TABLE calls (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id        UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  patient_id       UUID        REFERENCES patients(id),
  retell_call_id   TEXT        UNIQUE,
  direction        TEXT        CHECK (direction IN ('inbound','outbound')),
  call_type        TEXT        CHECK (call_type IN ('booking','recall','reminder','followup','insurance','general')),
  from_number      TEXT,
  to_number        TEXT,
  duration_seconds INTEGER,
  status           TEXT        CHECK (status IN ('initiated','ongoing','ended','failed')),
  outcome          TEXT        CHECK (outcome IN ('booked','rescheduled','cancelled','no_answer','callback','declined','completed')),
  appointment_id   UUID        REFERENCES appointments(id),
  transcript       TEXT,
  recording_url    TEXT,
  started_at       TIMESTAMPTZ,
  ended_at         TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- TABLE 5: sms_messages
-- ============================================================
CREATE TABLE sms_messages (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id        UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  patient_id       UUID        REFERENCES patients(id),
  twilio_sid       TEXT        UNIQUE,
  direction        TEXT        CHECK (direction IN ('inbound','outbound')),
  from_number      TEXT,
  to_number        TEXT,
  body             TEXT        NOT NULL,
  sms_type         TEXT        CHECK (sms_type IN ('reminder','recall','followup','insurance','confirmation','general')),
  appointment_id   UUID        REFERENCES appointments(id),
  status           TEXT        DEFAULT 'sent',
  patient_reply    TEXT,
  reply_sentiment  TEXT        CHECK (reply_sentiment IN ('positive','negative','neutral','concern')),
  created_at       TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- TABLE 6: jobs  (retry queue — critical for stability)
-- ============================================================
CREATE TABLE jobs (
  id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id      UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  job_type       TEXT        NOT NULL,                                  -- 'send_reminder','recall_call','insurance_check'
  payload        JSONB       NOT NULL,                                  -- all data needed to run the job
  status         TEXT        DEFAULT 'pending'
    CHECK (status IN ('pending','processing','done','failed')),
  attempts       INTEGER     DEFAULT 0,
  max_attempts   INTEGER     DEFAULT 3,
  error_message  TEXT,
  run_at         TIMESTAMPTZ DEFAULT NOW(),                             -- when to run (for scheduling)
  ran_at         TIMESTAMPTZ,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- TABLE 7: revenue_events
-- ============================================================
CREATE TABLE revenue_events (
  id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id      UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  event_type     TEXT        CHECK (event_type IN (
                               'missed_call_recovered',
                               'recall_booked',
                               'noshow_slot_filled',
                               'after_hours_booked',
                               'appointment_completed'
                             )),
  amount_cents   INTEGER     NOT NULL,
  appointment_id UUID        REFERENCES appointments(id),
  description    TEXT,
  created_at     TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================
-- WAITLIST
-- ============================================================
CREATE TABLE IF NOT EXISTS waitlist (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id        UUID        REFERENCES clinics(id) ON DELETE CASCADE,
  patient_id       UUID        REFERENCES patients(id) ON DELETE CASCADE,
  appointment_type TEXT        NOT NULL,
  preferred_dates  JSONB       DEFAULT '[]'::jsonb,
  status           TEXT        CHECK (status IN ('pending', 'fulfilled', 'cancelled')) DEFAULT 'pending',
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- TABLE 8: phone_pool (Twilio Number Provisioning)
-- ============================================================
CREATE TABLE IF NOT EXISTS phone_pool (
  id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  phone_number     TEXT        NOT NULL UNIQUE,
  is_assigned      BOOLEAN     DEFAULT false,
  assigned_to      UUID        REFERENCES clinics(id) ON DELETE SET NULL,
  assigned_at      TIMESTAMPTZ,
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- INDEXES for performance
-- ============================================================
CREATE INDEX idx_appointments_clinic_datetime ON appointments(clinic_id, datetime);
CREATE INDEX idx_appointments_status          ON appointments(clinic_id, status);
CREATE INDEX idx_patients_clinic_phone        ON patients(clinic_id, phone);
CREATE INDEX idx_patients_last_visit          ON patients(clinic_id, last_visit_date);
CREATE INDEX idx_calls_clinic                 ON calls(clinic_id, created_at DESC);
CREATE INDEX idx_jobs_pending                 ON jobs(status, run_at) WHERE status = 'pending';
CREATE INDEX idx_revenue_events_clinic        ON revenue_events(clinic_id, created_at);
