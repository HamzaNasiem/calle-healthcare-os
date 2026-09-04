# Bytelytic Clinic OS — CALL-E Hackathon Demo Script 🎬
**Target Category:** Most Practical Use Case ($4,000) / Grand Prize ($10,000)  
**Total Target Runtime:** 2 Minutes 30 Seconds (150s)  
**Tone:** Engineering-first, calm, authoritative, zero marketing buzzwords.

---

## ⏱️ Timeline & Scene Breakdown

### Scene 1: The Practical Clinical Problem (0:00 – 0:25)
**Screen:** Open on the Dashboard (`https://calle-healthcare-os.vercel.app`), cursor hovering over the "No-Shows & Cancellations" widget.

**Spoken Script (Voiceover):**
> "In an outpatient medical practice, roughly twenty percent of daily appointment slots end up as no-shows. 
> For a standard two-doctor clinic, that translates to over a hundred thousand dollars in lost provider time every year. 
> Front-desk staff currently spend three to four hours a day dialing patients manually to confirm appointments and chase cancellations. 
> To solve this, we integrated the official CALL-E Python SDK directly into Bytelytic Clinic OS—an existing, HIPAA-compliant practice management system."

---

### Scene 2: How We Integrated CALL-E SDK (0:25 – 0:50)
**Screen:** Quick switch to VS Code / GitHub showing `backend/src/services/calle_service.py` (specifically lines with `CalleClient` and `result_schema`). Then switch back to the browser at `/outbound-campaigns`.

**Spoken Script (Voiceover):**
> "Under the hood, we use the `calle-ai` Python client. 
> Instead of open-ended conversational bots, each campaign is bound to a strict JSON `result_schema`. 
> When CALL-E dials a patient, it conducts the conversation and extracts structured parameters—such as whether the patient confirmed, asked to reschedule, or declined—along with their preferred times and clinical notes. 
> These results are delivered back via webhook and written directly into our PostgreSQL database to update the patient's appointment status in real time."

---

### Scene 3: Live Outbound Call Execution (0:50 – 1:35)
**Screen:** In the browser on `/outbound-campaigns`, click the green **"Single Test Call"** button.
1. Enter your phone number.
2. Select campaign: **"24h Appointment Confirmation"**.
3. Point out the options: **"Instant Direct Dial (1s Ring)"** and **"CALL-E Autonomous Agent"**.
4. Click **"Execute Live Call"**.
5. Put your physical phone next to your microphone or show it on screen. The phone rings immediately.
6. Answer the phone on speaker:
   - **AI (CALL-E):** *"Hello, this is calling from Sunrise Medical Clinic. We have you scheduled for tomorrow at 10:30 AM. Can you confirm your attendance?"*
   - **You:** *"Yes, I will be there. Thank you."*
   - **AI (CALL-E):** *"Great, you're confirmed for 10:30 AM tomorrow. We look forward to seeing you. Goodbye."*
7. Hang up.
8. Show the dashboard automatically updating the call log and showing status `completed` with structured output `{"will_attend": "yes"}`.

**Spoken Script (Voiceover during call):**
> "Let's run a live 24-hour confirmation call. 
> I'll enter a recipient number and dispatch the campaign. 
> As you can hear, the call is placed instantly. 
> *(Let the 10-second phone dialogue play clearly).*
> As soon as the call concludes, CALL-E parses the intent, confirms the appointment in our database, and marks the slot verified without any human staff intervention."

---

### Scene 4: The 4 Purpose-Built Healthcare Campaigns (1:35 – 2:05)
**Screen:** Stay on `/outbound-campaigns`. Click briefly through the 4 campaign cards:
1. **24h Confirmation**
2. **2h Post-No-Show Recovery**
3. **30/60/90-Day Overdue Recall**
4. **Instant Cancellation Waitlist Backfill**

**Spoken Script (Voiceover):**
> "Beyond basic confirmations, we built four specific clinical campaign workflows:
> First, **Two-Hour Post-No-Show Recovery**—when an appointment is missed, the system calls within two hours to check in on the patient and offer immediate rebooking.
> Second, **Routine Care Recalls**—querying patients who haven't visited in thirty, sixty, or ninety days to schedule follow-up care.
> And third, **Instant Waitlist Backfill**—the moment a cancellation occurs, CALL-E immediately dials patients on the priority waitlist to backfill the empty slot before the provider's day starts."

---

### Scene 5: HIPAA Safeguards & Verification (2:05 – 2:25)
**Screen:** Navigate to `/settings` $\rightarrow$ **"Security & Auditing"** tab and briefly show the immutable audit log table.

**Spoken Script (Voiceover):**
> "Because this handles clinical data, we implemented strict healthcare safeguards:
> All system outputs pass through a `PHIScrubberFilter` to prevent patient identifiers from appearing in server logs. 
> Call audio links are subject to a strict twenty-four-hour ephemeral retention policy. 
> And every outbound dispatch and status change generates an immutable cryptographic audit record."

---

### Scene 6: Conclusion (2:25 – 2:40)
**Screen:** Switch back to the main Overview Dashboard showing clean stats and provider schedule.

**Spoken Script (Voiceover):**
> "Bytelytic Clinic OS with CALL-E is live today. 
> Both the frontend on Vercel and backend on Render are fully deployed, public, and connected to our live PostgreSQL database. 
> The complete source code, API documentation, and test scripts are available on GitHub. 
> Thank you for reviewing our submission."

---

## 🎯 Recording Tips for a Flawless Submission
1. **Resolution:** 1080p (1920x1080) at 60fps or 30fps.
2. **Audio:** Use a clean USB microphone or headset. Avoid background noise.
3. **Pacing:** Speak at a steady, natural pace. Do not rush.
4. **Phone audio:** When doing the live call test (Scene 3), put your phone on speaker near the mic so the judges can hear both sides clearly.
5. **No editing tricks:** Keeping it as a single continuous recording or minimal cuts proves to the judges that the system is 100% real and working.
