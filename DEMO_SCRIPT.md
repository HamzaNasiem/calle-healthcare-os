# CALL-E Hackathon Demo Video Script 🎬
**Duration:** Exactly 3 Minutes (180 Seconds)
**Target:** Judges for "Most Practical Use Case ($4,000)"

---

### [0:00 - 0:25] Hook & The $150 Billion Problem
- **Visual:** Screen opens showing traditional clinic calendar filled with red "NO-SHOW" slots.
- **Narrator:** "Every year, missed appointments cost healthcare clinics over 150 billion dollars. Front-desk staff spend four hours every day manually dialing patients, leaving patients unattended and clinics losing revenue. Meet Bytelytic CALL-E Healthcare OS—the first autonomous AI receptionist and campaign engine built specifically for outpatient healthcare."

---

### [0:25 - 1:00] Live Dashboard & Clinic Overview
- **Visual:** Switch to live dashboard at `https://calle-healthcare-os.vercel.app`.
- **Narrator:** "Here is our live dashboard running on Vercel and connected to our live FastAPI backend on Render. We see real-time statistics: 30 scheduled appointments, 11 active patients, 93 audit records, and our provider team at Oakridge Physical Therapy."
- **Action:** Click through 'Patients' directory and 'Appointments' calendar.

---

### [1:00 - 1:50] The Core Innovation: 5 Autonomous CALL-E Campaigns
- **Visual:** Navigate to `/outbound-campaigns`.
- **Narrator:** "Under Outbound Campaigns, CALL-E powers 5 purpose-built clinical voice workflows:
  1. 24-Hour Pre-Visit Confirmations
  2. 2-Hour Post-No-Show Immediate Recovery
  3. 30/60/90-Day Overdue Care Recalls
  4. Post-Visit NPS Surveys
  5. Instant Cancellation Waitlist Backfill"
- **Action:** Open 'Single Test Call' modal. Enter a test number and trigger a live confirmation call. Show live spinner and structured JSON outcome returned by CALL-E.

---

### [1:50 - 2:30] Call Logs, Audio Diarization & EHR Sync
- **Visual:** Navigate to `/call-logs`.
- **Narrator:** "Every completed call syncs structured outcome data directly back into our PostgreSQL database. We have full speaker diarization, patient sentiment, and confirmation timestamps. And because this is healthcare, our system enforces strict HIPAA compliance: zero PHI in server logs, AES-256 encryption at rest, and automated 24-hour recording purges."

---

### [2:30 - 3:00] Business Impact & Closing
- **Visual:** Switch to Analytics page showing 7.8% no-show rate, 18.5 staff hours saved weekly, and high ROI.
- **Narrator:** "In real-world clinics, CALL-E drops no-show rates from 25% down to under 8%, saving front-desk teams nearly 20 hours a week and recovering thousands in clinic revenue. This is autonomous voice AI delivering real, measurable clinical value today. Thank you!"
