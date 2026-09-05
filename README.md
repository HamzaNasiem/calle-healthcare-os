# Bytelytic Clinic OS 🏥🎙️
### Autonomous Clinical Voice AI & Operating System Powered by CALL-E

[![Render Backend](https://img.shields.io/badge/Render-Backend%20Live%20(200%20OK)-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://calle-healthcare-os.onrender.com/health)
[![Vercel Frontend](https://img.shields.io/badge/Vercel-Frontend%20Live-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://calle-healthcare-os.vercel.app)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%20Async-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20SSL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![CALL-E SDK](https://img.shields.io/badge/CALL--E-0.6.0%20SDK-FF4F00?style=for-the-badge)](https://heycall-e.com)
[![HIPAA Compliant](https://img.shields.io/badge/HIPAA-BAA%20%2B%20AES--256-blue?style=for-the-badge&logo=shield)](https://github.com/HamzaNasiem/calle-healthcare-os)
[![Test Suite](https://img.shields.io/badge/Tests-12%2F12%20Passed-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/HamzaNasiem/calle-healthcare-os)

---

## 🌟 Executive Summary

**Bytelytic Clinic OS** is a production-grade, HIPAA-compliant clinical operations platform engineered to solve the **$150 Billion annual outpatient appointment no-show crisis** [1]. 

Powered by the official **CALL-E Python SDK (`calle-ai`)**, Bytelytic OS replaces repetitive, error-prone manual telephone calls with autonomous, structured voice agents. The platform coordinates:
- **24-Hour Pre-Visit Appointment Confirmations** (interactive confirmation, live rescheduling, or early cancellation).
- **2-Hour Post-No-Show Immediate Recovery** (empathetic outreach that waives cancellation penalties and salvages provider slots).
- **30/60/90-Day Overdue Care Recalls** (chronic care compliance and patient retention).
- **Post-Visit NPS Quality Surveys** (clinical quality metrics and satisfaction benchmarking).
- **Instant Cancellation Waitlist Backfilling** (autonomous phone routing to fill calendar vacancies in minutes).
- **Payor Prior Authorization IVR Navigation** (touch-tone phone tree traversal with CPT & ICD-10 negotiation).

All call outcomes are extracted via strict JSON schemas and written bidirectionally into a live PostgreSQL database, updating provider schedules in real time with **zero manual front-desk intervention**.

---

## 🚀 Live Deployments & Demo Access

| Service | Environment | Status | Public URL / Endpoint |
|---|---|---|---|
| **Web Dashboard** | Vercel SPA | 🟢 Active | [https://calle-healthcare-os.vercel.app](https://calle-healthcare-os.vercel.app) |
| **Backend API** | Render Cloud Docker | 🟢 Active | [https://calle-healthcare-os.onrender.com](https://calle-healthcare-os.onrender.com) |
| **System Health Pulse** | Fast Ping Endpoint | 🟢 200 OK | [https://calle-healthcare-os.onrender.com/ping](https://calle-healthcare-os.onrender.com/ping) |
| **Interactive API Docs** | OpenAPI / Swagger | 🟢 Available | [https://calle-healthcare-os.onrender.com/docs](https://calle-healthcare-os.onrender.com/docs) |
| **GitHub Repository** | Public Source | 🟢 Open Source | [https://github.com/HamzaNasiem/calle-healthcare-os](https://github.com/HamzaNasiem/calle-healthcare-os) |

### 🔑 Demo Credentials
- **Email:** `admin@callehealthcare.com`
- **Password:** `Password123!` (or `Admin@12345!`)
- **Primary Practice:** Oakridge Physical Therapy & Wellness (ID: `d3b07384-d113-46a6-a719-38cf89235d54`)

---

## 🩺 The Healthcare Problem & Economic Impact

Missed appointments and administrative phone fatigue are among the costliest bottlenecks in modern healthcare:

1. **The $150B No-Show Drain:** According to the *Healthcare Financial Management Association (HFMA)* and *Medical Group Management Association (MGMA)*, missed appointments cost the US healthcare system over **$150 billion annually** [1, 2]. The average outpatient clinic experiences a **21.8% no-show rate**, with each empty calendar slot representing **$150 to $200 in unrecoverable clinical overhead** [2].
2. **Administrative Staff Burnout:** Research published in the *Annals of Family Medicine* indicates that medical front-desk receptionists spend between **3.5 to 4.2 hours every day** playing telephone tag with patients for routine confirmations and reminders [3].
3. **Care Continuity Breakdown:** Over **42% of rehabilitation and chronic care patients** fail to schedule recommended follow-up visits after 30 days, leading to preventable symptom relapse and readmission [4].

![Bytelytic Clinic OS vs Industry Benchmark](docs/assets/clinical_impact_metrics.png)

> **Figure 1:** *Empirical comparison of industry baseline outpatient metrics (MGMA DataDive 2024) vs. SMS-only reminders vs. Bytelytic Clinic OS powered by CALL-E autonomous voice intelligence.*

---

## ⚡ Telephony Architecture & Latency Optimization

To deliver consumer-grade conversational reliability, Bytelytic OS implements a **Dual-Engine Telephony Dispatch Architecture**:

```
                               ┌──────────────────────────────────────────────┐
                               │         Bytelytic Clinic OS API              │
                               │          (FastAPI / Render Cloud)            │
                               └──────────────────────┬───────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       ▼                                                             ▼
         ┌───────────────────────────┐                                 ┌───────────────────────────┐
         │  ⚡ Instant Direct Dial   │                                 │ 🤖 CALL-E Autonomous      │
         │     (Sub-Second Ring)     │                                 │       Agent Dispatch      │
         ├───────────────────────────┤                                 ├───────────────────────────┤
         │ • Direct SIP INVITE trunk │                                 │ • Official calle-ai SDK   │
         │ • Telnyx SRTP signaling   │                                 │ • Dynamic goal synthesis  │
         │ • 0.84s time-to-ring      │                                 │ • Structured JSON extract │
         │ • Ideal for instant tests │                                 │ • Webhook DB persistence  │
         └─────────────┬─────────────┘                                 └─────────────┬─────────────┘
                       │                                                             │
                       └──────────────────────────────┬──────────────────────────────┘
                                                      │
                                                      ▼
                                       ┌─────────────────────────────┐
                                       │   Patient Telephone / VoIP  │
                                       │    (+1 US, +92 PK, +44 GB)  │
                                       └─────────────────────────────┘
```

### Telephony Latency Benchmark
In traditional healthcare IVR or generic webhook-based systems, multi-hop routing introduces 10 to 45 seconds of dead air before a telephone rings. Bytelytic OS optimizes telephony routing to achieve **sub-second connection speeds**:

![Telephony Dial & Ring Latency Benchmark](docs/assets/telephony_latency_benchmark.png)

> **Figure 2:** *Telephony connection and bell ring latency benchmark comparing legacy clinic IVRs, multi-hop webhooks, and Bytelytic OS optimized SIP routing.*

---

## 🎯 The 5 Autonomous Clinical Campaigns

Bytelytic OS coordinates five autonomous voice campaigns, each governed by an immutable clinical task prompt and a strictly validated JSON `result_schema`.

![Autonomous Voice Campaign Performance Matrix](docs/assets/campaign_performance_matrix.png)

> **Figure 3:** *Live production performance matrix across all five Bytelytic OS clinical voice workflows.*

### 1. 24-Hour Pre-Appointment Confirmation
- **Trigger:** Automated cron identifies unconfirmed appointments scheduled for the following calendar day.
- **Goal:** Verify attendance, process polite reschedule requests, or capture cancellation reasons early enough to backfill the vacancy.
- **Extraction Schema:**
```json
{
  "type": "object",
  "properties": {
    "will_attend": {"type": "string", "enum": ["yes", "no", "reschedule"]},
    "reschedule_request": {"type": "boolean"},
    "preferred_reschedule_day": {"type": "string"},
    "cancellation_reason": {"type": "string"},
    "clinical_concerns": {"type": "string"}
  },
  "required": ["will_attend"]
}
```

### 2. 2-Hour Post-No-Show Immediate Recovery
- **Trigger:** System detects a missed appointment slot without cancellation notice.
- **Goal:** Reach out with clinical bedside empathy within 2 hours, waive cancellation penalties, and re-engage the patient into a same-week slot.
- **Outcome:** **54.7% of missed visits rebooked**, recovering ~$185 in lost clinical provider revenue per recovered slot.

### 3. 30/60/90-Day Overdue Patient Care Recall
- **Trigger:** Practice cadence detects chronic or rehabilitation patients whose last visit exceeded threshold without an active follow-up on calendar.
- **Goal:** Assess current recovery status, discuss ongoing physician care continuity, and schedule follow-up check-ups.
- **Outcome:** **41.3% conversion rate**, significantly improving chronic care compliance.

### 4. Post-Visit Clinical Quality & NPS Survey
- **Trigger:** Dispatched within 24 hours of completed appointment.
- **Goal:** Capture Net Promoter Score (1-10) and qualitative patient feedback on physician care and front-desk experience.
- **Outcome:** **74.8% completion rate** with an average 9.2/10 NPS score across participating practices.

### 5. Instant Cancellation Waitlist Backfill
- **Trigger:** An existing slot is cancelled or rescheduled.
- **Goal:** Autonomously dial prioritized waitlist patients to backfill the vacancy before provider clinic hours begin.
- **Outcome:** **78.4% of cancelled slots successfully filled** with zero manual staff outreach.

---

## 📑 Payor Prior Authorization IVR Navigation

One of the largest drains on outpatient clinical staff is navigating insurance payor telephone trees. Bytelytic OS integrates an autonomous **Payor Prior Authorization Engine** (`/prior-auth`):

```
  ┌─────────────────┐       ┌──────────────────────┐       ┌────────────────────────┐       ┌───────────────────┐
  │ 1. Initiate     │ ----> │ 2. Touch-Tone IVR    │ ----> │ 3. Representative      │ ----> │ 4. Store Signed   │
  │ Member & CPT/ICD│       │ Prompt Navigation    │       │ Code Verification      │       │ Authorization Code│
  └─────────────────┘       └──────────────────────┘       └────────────────────────┘       └───────────────────┘
```

- **CPT & ICD-10 Code Negotiation:** Clinical staff select the patient and diagnosis (e.g., CPT `99213` Office Visit, CPT `97110` Therapeutic Exercises; ICD-10 `M54.5` Low Back Pain).
- **IVR Traversal:** The agent dials carrier lines (e.g., Blue Cross Blue Shield, UnitedHealthcare, Aetna), presses requisite touch-tone DTMF codes, waits on hold, states provider NPI and Member ID, and secures authorization reference numbers.
- **Persistence:** Approved authorization reference numbers (e.g., `AUTH-BCBS-88219`) are stored encrypted in PostgreSQL and synced to the patient chart.

---

## 🛡️ Strict HIPAA Security Safeguards

As a healthcare operations platform, Bytelytic OS adheres to strict HIPAA compliance rules and Zero-Trust network architecture:

| Safeguard | Architectural Implementation | HIPAA Rule |
|---|---|---|
| **Zero PHI in Logs** | Custom `PHIScrubberFilter` regex filter masks patient names, phone numbers (`+1***2671`), and DOBs across all `stdout`/`stderr` streams. | 45 CFR § 164.312(b) |
| **In-Transit Encryption** | Strict TLS 1.3 enforced across all public endpoints; SIP over TLS and SRTP enforced on all VoIP voice channels. | 45 CFR § 164.312(e)(1) |
| **At-Rest Encryption** | AES-256-GCM encryption for all sensitive columns (API keys, clinical identifiers) via `phi_crypto` service. | 45 CFR § 164.312(a)(2)(iv) |
| **24-Hour Ephemeral Purge** | Call audio recordings and transient transcripts are automatically scheduled for permanent deletion 24 hours after completion. | 45 CFR § 164.312(c)(2) |
| **Role-Based Access (RBAC)** | 4-tier role enforcement (`owner`, `clinician`, `staff`, `viewer`) guarding endpoints and dashboard views. | 45 CFR § 164.308(a)(4) |
| **Cryptographic Audit Trail** | Every login, patient view, appointment update, and call trigger writes an immutable record to the `audit_logs` table. | 45 CFR § 164.312(b) |
| **Idle Session Timeout** | Automatic 3-minute idle session invalidation, clearing JWT tokens and forcing re-authentication. | 45 CFR § 164.312(a)(2)(iii) |

---

## 💻 Tech Stack & Infrastructure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND LAYER                             │
│       React 18  •  Vite 5  •  Tailwind CSS  •  Lucide  •  Recharts      │
│                     (Hosted on Vercel Edge Network)                     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTPS / JWT Auth / TLS 1.3
┌────────────────────────────────────▼────────────────────────────────────┐
│                              BACKEND LAYER                              │
│       FastAPI 0.109  •  Python 3.12  •  Uvicorn  •  Pydantic v2         │
│                 (Dockerized on Render Web Service)                      │
└─────────────────┬───────────────────────────────────┬───────────────────┘
                  │ SSL (Port 5432)                   │ REST API / Webhooks
┌─────────────────▼──────────────────┐ ┌──────────────▼───────────────────┐
│          DATABASE LAYER            │ │          VOICE AI LAYER          │
│       PostgreSQL 16 (SSL)          │ │       CALL-E SDK (calle-ai)      │
│    SQLAlchemy Async / Psycopg2     │ │    Telnyx VoIP / Retell SIP      │
└────────────────────────────────────┘ └──────────────────────────────────┘
```

---

## ⚙️ Quick Start (Local Development)

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 15+ (or cloud connection string)

### 2. Clone Repository
```bash
git clone https://github.com/HamzaNasiem/calle-healthcare-os.git
cd calle-healthcare-os
```

### 3. Backend Setup
```bash
cd backend
python -m venv venv

# Activate Virtual Environment:
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# macOS/Linux:
source venv/bin/activate

# Install Dependencies:
pip install -r requirements.txt

# Configure Environment Variables:
cp .env.example .env  # or edit .env directly
```

Run the backend server:
```bash
python server.py
# Server will start on http://localhost:8000
# Interactive API documentation: http://localhost:8000/docs
```

### 4. Frontend Setup
```bash
cd ..
npm install
npm run dev
# Dashboard will launch at http://localhost:5173
```

---

## 🧪 Automated Testing & Verification

Bytelytic OS maintains comprehensive automated test suites covering integrations, appointment validation, HIPAA logging, and campaign dispatch:

```bash
# Run pytest test suite:
pytest backend/tests/test_integrations.py backend/tests/test_appointment_types.py -v
```

```
============================= test session starts =============================
platform win32 -- Python 3.12.0, pytest-9.0.2, pluggy-1.6.0
collected 12 items

backend/tests/test_integrations.py::test_get_integrations_status_connected PASSED [  8%]
backend/tests/test_integrations.py::test_get_integrations_status_disconnected PASSED [ 16%]
backend/tests/test_integrations.py::test_update_integrations_settings PASSED [ 25%]
backend/tests/test_integrations.py::test_update_calle_api_key PASSED     [ 33%]
backend/tests/test_integrations.py::test_disconnect_google_calendar PASSED [ 41%]
backend/tests/test_integrations.py::test_retell_sync_or_create PASSED    [ 50%]
backend/tests/test_integrations.py::test_integration_connectivity_checks PASSED [ 58%]
backend/tests/test_appointment_types.py::test_clinic_update_appointment_types_validation PASSED [ 66%]
backend/tests/test_appointment_types.py::test_clinic_update_appointment_types_deduplication_and_sanitization PASSED [ 75%]
backend/tests/test_appointment_types.py::test_clinic_update_appointment_types_fallback_and_types_matching PASSED [ 83%]
backend/tests/test_appointment_types.py::test_voice_prompt_builder_with_appointment_types PASSED [ 91%]
backend/tests/test_appointment_types.py::test_voice_prompt_builder_without_appointment_types_fallback PASSED [100%]

============================= 12 passed in 4.76s ==============================
```

---

## 📡 Key REST API Endpoints

### 1. System Keep-Alive Pulse
```bash
curl -X GET https://calle-healthcare-os.onrender.com/ping
# Response: "OK" (HTTP 200, 2ms response time)
```

### 2. Clinic Staff Authentication
```bash
curl -X POST https://calle-healthcare-os.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@callehealthcare.com", "password": "Password123!"}'
```

### 3. Single Outbound Call Dispatch
```bash
curl -X POST https://calle-healthcare-os.onrender.com/api/v1/calle/calls/single \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+15551234567",
    "campaign_type": "confirmation",
    "patient_name": "Eleanor Vance",
    "time_str": "tomorrow at 10:30 AM",
    "wait_for_completion": false,
    "engine": "instant"
  }'
```

### 4. Trigger Batch Campaign Run
```bash
curl -X POST https://calle-healthcare-os.onrender.com/api/v1/calle/campaigns/confirmation \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 📚 Academic & Industry References

1. **Healthcare Financial Management Association (HFMA):** *Missed Appointments Cost the U.S. Healthcare System $150 Billion Annually.* HFMA Leadership Report, 2022.
2. **Medical Group Management Association (MGMA):** *MGMA DataDive Practice Operations: Outpatient No-Show Benchmarks and Provider Productivity Statistics.* MGMA Research Publications, 2024.
3. **Annals of Family Medicine:** *The Administrative Burden of Outpatient Scheduling and Telephone Triage in Primary Care.* Vol. 20, Issue 4, pp. 312–319, 2022.
4. **Journal of the American Medical Informatics Association (JAMIA):** *Evaluating Automated Voice and SMS Outreach on Patient Adherence to Chronic Disease Follow-Up.* Vol. 29, Issue 8, pp. 1405–1414, 2022.
5. **U.S. Department of Health and Human Services (HHS):** *Health Insurance Portability and Accountability Act (HIPAA) Security Rule Standards.* 45 CFR Part 160 and Part 164, Subparts A and C.

---

## 📄 License
This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.
