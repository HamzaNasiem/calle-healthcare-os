# CALL-E Healthcare OS — Autonomous Medical Phone Operations

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CALL-E SDK](https://img.shields.io/badge/CALL--E-v0.6.0-emerald.svg)](https://docs.heycall-e.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-teal.svg)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-blue.svg)](https://react.dev)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-3.4-sky.svg)](https://tailwindcss.com)

**Autonomous AI Voice Operations for Medical Practices:** 24-Hour Appointment Confirmation, 2-Hour No-Show Recovery, 30/60/90-Day Patient Recall, Post-Visit NPS Satisfaction Surveys, and Commercial Payor Prior Authorization IVR Navigation.

---

## 🏥 The Problem

U.S. medical clinics lose over **$150 billion annually** due to patient no-shows, while front-desk receptionists spend **15+ hours per week** stuck on repetitive phone calls and insurance payor hold lines. 

Traditional rigid IVR scripts fail when patients give natural responses or need to negotiate dates.

---

## ⚡ The Solution: CALL-E Healthcare OS

Bytelytic CALL-E Healthcare OS connects healthcare practice EHR systems to CALL-E's autonomous voice infrastructure to run goal-driven patient phone workflows:

1. **24-Hour Appointment Confirmation:** Empathetically calls patients 24 hours prior to visits, verifies attendance, captures reschedule windows, and enforces pre-visit instructions.
2. **2-Hour Post-No-Show Recovery:** Automatically engages missed patients within 2 hours to offer immediate slot rebooking.
3. **30/60/90-Day Preventive Recalls:** Reactivates overdue patients for routine care.
4. **Post-Visit Patient Satisfaction (NPS):** Captures 1-10 Net Promoter Scores and verbatim clinical feedback.
5. **Insurance Prior Auth Payor IVR Navigator:** Dials commercial insurers, navigates multi-tier IVR keypad menus, negotiates with insurer representatives, and extracts authorization approval codes directly into EHR records.

---

## 🛠️ Architecture & Stack

- **Frontend:** React 18, Vite, Tailwind CSS, Lucide Icons, Recharts, Web Speech API Simulator.
- **Backend:** FastAPI, Python, `calle-ai` SDK (`CalleClient.calls.create_and_wait`), PostgreSQL.
- **Security & HIPAA:** AES-256 encrypted payor data, PHIScrubber filtering, zero PHI in stdout.

---

## 🚀 Quickstart

### Frontend

```bash
npm install
npm run dev
```

The frontend dashboard launches on `http://127.0.0.1:5173`.

### Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 🧪 Demo Credentials

- **Email:** `owner@sunrisehealth.com`
- **Password:** `Password123!`
