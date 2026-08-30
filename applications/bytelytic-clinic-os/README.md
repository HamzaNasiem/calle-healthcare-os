# Bytelytic Clinic OS — CALL-E Autonomous Healthcare Receptionist

## 🏥 Application Details
- **Name:** Bytelytic Clinic OS
- **Category:** Healthcare & Clinical Operations
- **Target Category:** Most Practical Use Case
- **Live Demo:** [https://calle-healthcare-os.vercel.app](https://calle-healthcare-os.vercel.app)
- **Backend API:** [https://calle-healthcare-os.onrender.com/docs](https://calle-healthcare-os.onrender.com/docs)
- **Repository:** [https://github.com/HamzaNasiem/calle-healthcare-os](https://github.com/HamzaNasiem/calle-healthcare-os)

---

## 🌟 What It Does
Bytelytic Clinic OS integrates **CALL-E Phone Call Agents** into outpatient medical clinics to eliminate no-shows and automate clinical voice outreach:

1. **24H Appointment Confirmations:** Automated calls to verify tomorrow's patient schedule.
2. **2H No-Show Recovery:** Immediate empathetic callbacks for missed appointments.
3. **Care Recalls:** Re-engaging patients overdue for follow-up physical therapy.
4. **Post-Visit NPS Surveys:** Voice surveys capturing patient satisfaction metrics.
5. **Instant Waitlist Fill:** Auto-dialing standby patients when cancellations occur.

---

## 🛠️ CALL-E SDK Usage
- **SDK Package:** `calle-ai>=0.2.0`
- **Endpoints:** `client.calls.create()`, `client.calls.create_and_wait()`, webhook status synchronization
- **Structured Schema Extraction:** Extracts `appointment_status`, `wants_rebook`, `nps_score`, and timestamps directly into PostgreSQL.

---

## 💻 Tech Stack
- **Frontend:** React, Vite, Tailwind CSS (Vercel)
- **Backend:** FastAPI, Python 3.11, PostgreSQL (Render)
- **Voice AI:** CALL-E SDK + Telnyx VoIP
