# CALL-E Healthcare OS 🏥🎙️
### Autonomous AI Voice Receptionist & Clinical Campaign Engine for Healthcare Practices

[![Render Backend](https://img.shields.io/badge/Render-Backend%20Live-46E3B7?style=for-the-badge&logo=render&logoColor=white)](https://calle-healthcare-os.onrender.com/health)
[![Vercel Frontend](https://img.shields.io/badge/Vercel-Frontend%20Live-000000?style=for-the-badge&logo=vercel&logoColor=white)](https://calle-healthcare-os.vercel.app)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20SSL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![CALL-E SDK](https://img.shields.io/badge/CALL--E-0.2.0%20SDK-FF4F00?style=for-the-badge)](https://heycall-e.com)
[![HIPAA Compliant](https://img.shields.io/badge/HIPAA-BAA%20%2B%20AES--256-blue?style=for-the-badge&logo=shield)](https://github.com/HamzaNasiem/calle-healthcare-os)

---

## 🌟 Executive Summary

**Bytelytic CALL-E Healthcare OS** is a production-grade, HIPAA-compliant clinical operations platform designed to solve the **$150B/year outpatient appointment no-show crisis**. 

Powered by **CALL-E Autonomous Voice Agents**, the system autonomously executes structured phone campaigns—confirming next-day visits, recovering same-day missed appointments, re-engaging overdue care recalls, surveying recent visits, and backfilling cancellations from live waitlists—syncing structured outcomes directly into EHR databases with zero staff overhead.

---

## 🚀 Live Deployments & Demo Access

| Service | Status | Endpoint / URL |
|---|---|---|
| **Web Dashboard** | 🟢 Live (Vercel) | [https://calle-healthcare-os.vercel.app](https://calle-healthcare-os.vercel.app) |
| **API Backend** | 🟢 Live (Render) | [https://calle-healthcare-os.onrender.com](https://calle-healthcare-os.onrender.com) |
| **System Health** | 🟢 200 OK | [https://calle-healthcare-os.onrender.com/health](https://calle-healthcare-os.onrender.com/health) |
| **Interactive API Docs** | 🟢 Swagger UI | [https://calle-healthcare-os.onrender.com/docs](https://calle-healthcare-os.onrender.com/docs) |
| **GitHub Repository** | 🟢 Public | [https://github.com/HamzaNasiem/calle-healthcare-os](https://github.com/HamzaNasiem/calle-healthcare-os) |

### 🔑 Demo Credentials
- **Email:** `admin@callehealthcare.com`
- **Password:** `Admin@12345!`

---

## 🩺 The Healthcare Problem & Opportunity

1. **25% Average No-Show Rate:** Outpatient clinics lose up to $200 per empty appointment slot.
2. **Staff Burnout:** Front-desk receptionists spend 3 to 4 hours daily manually dialing patients for confirmation and recall reminders.
3. **Broken Patient Retention:** 40% of patients overdue for follow-up care or chronic checkups fall through the cracks without structured recall workflows.

---

## ⚡ Key CALL-E Voice Campaigns

```
                  ┌─────────────────────────────────────────┐
                  │      CALL-E Healthcare AI Engine        │
                  └────────────────────┬────────────────────┘
                                       │
        ┌──────────────┬───────────────┼──────────────┬──────────────┐
        ▼              ▼               ▼              ▼              ▼
 ┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐┌──────────────┐
 │ 24H Pre-Visit││ 2H No-Show   ││ 30/60/90-Day ││ Post-Visit   ││ Instant Slot │
 │ Confirmation ││ Recovery     ││ Care Recall  ││ NPS Survey   ││ Backfill     │
 └──────────────┘└──────────────┘└──────────────┘└──────────────┘└──────────────┘
```

### 1. 24-Hour Pre-Appointment Confirmation
- **Trigger:** Cron scheduler identifies appointments scheduled for tomorrow.
- **AI Task:** Calls patient warmly, confirms appointment date/time, handles reschedule requests, or processes early cancellations.
- **Outcome Schema:** `appointment_status` (confirmed / rescheduled / cancelled), `preferred_reschedule_time`, `cancellation_reason`.

### 2. 2-Hour Post-No-Show Immediate Recovery
- **Trigger:** System detects patient missed scheduled time without prior notice.
- **AI Task:** Reaches out with bedside empathy, checks patient status, and offers immediate 1-click rebooking into open slots.
- **Outcome Schema:** `wants_rebook` (bool), `preferred_time`, `reason_for_no_show`.

### 3. 30/60/90-Day Patient Recall
- **Trigger:** Automated care cadence detects overdue physical therapy or routine follow-up.
- **AI Task:** Inquires about recovery status, explains care plan continuity, and schedules the next visit.
- **Outcome Schema:** `interested` (bool), `preferred_day`, `preferred_time`, `notes`.

### 4. Post-Visit Satisfaction & NPS Survey
- **Trigger:** Dispatched within 24 hours of completed appointment.
- **AI Task:** Conducts concise 60-second satisfaction rating on clinical quality and Net Promoter Score.
- **Outcome Schema:** `nps_score` (1-10), `main_feedback`, `would_recommend` (bool).

### 5. Instant Cancellation Waitlist Backfill
- **Trigger:** Calendar slot becomes vacant due to cancellation.
- **AI Task:** Dispatches phone calls to waitlisted patients in order of urgency to fill the vacant doctor time slot immediately.

---

## 🏗️ System Architecture

```mermaid
graph TD
    Client[React + Vite Frontend\nVercel] -->|HTTPS / JWT Auth| API[FastAPI Backend\nRender Docker]
    API -->|Async SQLAlchemy / SSL| DB[(PostgreSQL 16\nRender Cloud)]
    API -->|CALL-E Python SDK| CalleAPI[CALL-E Voice Platform\napi.heycall-e.com]
    CalleAPI -->|Telnyx / SIP SRTP| PatientPhone((Patient Mobile / Landline))
    CalleAPI -->|Structured Webhooks| API
    API -->|AES-256 GCM Audit| AuditLog[(HIPAA Audit Logs)]
```

---

## 🛡️ Strict HIPAA Security Safeguards

- **No PHI in Server Logs:** `PHIScrubberFilter` automatically sanitizes patient identifiers, phone numbers, and dates of birth before logging.
- **In-Transit & At-Rest Encryption:** TLS 1.3 enforced on all API routes; database connections encrypted via SSL (`sslmode=require`); data-at-rest encrypted with AES-256-GCM.
- **Immutable Audit Logging:** Every patient access, call dispatch, and status modification writes a signed record to `audit_logs`.
- **Role-Based Access Control (RBAC):** Multi-tenant isolation ensuring clinic data boundaries are enforced at the database query level.

---

## 💻 Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS, Lucide Icons, Recharts, Axios |
| **Backend** | Python 3.11, FastAPI, Uvicorn, Gunicorn, Pydantic v2, Asyncpg |
| **Telephony / Voice AI** | CALL-E AI SDK (`calle-ai>=0.2.0`), Webhooks, Telnyx VoIP |
| **Database & Cache** | PostgreSQL 16 SSL, SQLAlchemy Async ORM, Psycopg2 |
| **Deployment** | Vercel (Frontend SPA), Render Cloud (Backend Container + DB) |

---

## ⚙️ Quick Start Guide (Local Development)

### 1. Clone the repository
```bash
git clone https://github.com/HamzaNasiem/calle-healthcare-os.git
cd calle-healthcare-os
```

### 2. Backend Setup
```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in `backend/`:
```env
DATABASE_URL=postgresql+asyncpg://calle_user:password@hostname/bytelytic_clinic_db?sslmode=require
CALLE_API_KEY=iams_live_your_calle_api_key
CALLE_BASE_URL=https://api.heycall-e.com
JWT_SECRET=your_jwt_secret_key
ENCRYPTION_KEY=your_base64_aes256_key
ENVIRONMENT=production
CORS_ORIGINS=*
```

Run the backend:
```bash
python server.py
```

### 3. Frontend Setup
```bash
cd ../dashboard
npm install
npm run dev
```

---

## 📡 Key API Endpoints

```bash
# Health Check
curl -X GET https://calle-healthcare-os.onrender.com/health

# Login & Token Generation
curl -X POST https://calle-healthcare-os.onrender.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@callehealthcare.com", "password": "Admin@12345!"}'

# Dispatch Single CALL-E Test Call
curl -X POST https://calle-healthcare-os.onrender.com/api/v1/calls/single \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "+15551234567",
    "patient_name": "Eleanor Vance",
    "campaign_type": "confirmation",
    "appointment_time": "Tomorrow at 10:00 AM"
  }'
```

---

## 🏆 Hackathon Submission Details

- **Hackathon:** CALL-E: Your Code Is Calling ($10,000 Prize Pool)
- **Target Category:** Most Practical Use Case ($4,000)
- **Submission Date:** September 2026
- **Devpost Entry:** Bytelytic CALL-E Clinic OS
- **Awesome Agents PR:** `applications/bytelytic-clinic-os`

---

## 📄 License
This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
