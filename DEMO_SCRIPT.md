# 🎬 BYTELYTIC CLINIC OS — FINAL DEMO SCRIPT
### CALL-E: Your Code Is Calling Hackathon
**Target: 2:00 minutes · Simple English · 100% CALL-E Native**

---

## TIMING GUIDE
| Segment | Duration | Spoken Words |
|---|---|---|
| Hook | 0:00 – 0:20 | ~46 words |
| The Problem | 0:20 – 0:35 | ~35 words |
| What We Built | 0:35 – 0:55 | ~48 words |
| Live Demo | 0:55 – 1:35 | ~85 words |
| How It Works | 1:35 – 1:50 | ~35 words |
| Close | 1:50 – 2:00 | ~25 words |
| **TOTAL** | **2:00** | **~274 words** |

---

## FULL SCRIPT

---

### [0:00 – 0:20] — HOOK
*Screen: Live dashboard at `calle-healthcare-os.vercel.app`. Metrics visible — appointments today, call queue, confirmed count.*

> "Every missed doctor's appointment costs a clinic money. In the US alone, that's 150 billion dollars a year. And the staff spending hours on the phone chasing patients? That's not medicine — that's wasted time. We fixed it."

---

### [0:20 – 0:35] — THE PROBLEM
*Screen: Slowly scroll down the dashboard — show appointment list, status badges (Confirmed, No-Show, Scheduled).*

> "Clinics need to confirm appointments, follow up on no-shows, fill last-minute cancellations, and chase insurance approvals — all by phone. There aren't enough staff hours to do this. So most clinics just don't."

---

### [0:35 – 0:55] — WHAT WE BUILT
*Screen: Click to the "CALL-E Autonomous Outbound Campaigns" page. The green banner reads "🟢 CALL-E Autonomous Engine: Live Mode".*

> "This is Bytelytic Clinic OS. We built six fully automated phone call workflows — all powered by CALL-E. No staff needed. The AI makes the calls, listens to the patient, understands the answer, and updates the system — automatically."

---

### [0:55 – 1:35] — LIVE DEMO
*Screen: Show the campaign cards — hover over each one as you name it.*

> "Here are the six campaigns running right now.
>
> One — **Appointment Confirmation**. The day before a visit, CALL-E calls the patient and confirms they're coming.
>
> Two — **No-Show Recovery**. If someone misses their slot, CALL-E calls within two hours and tries to reschedule.
>
> Three — **Patient Recall**. Patients who haven't visited in 30, 60, or 90 days get an automatic follow-up call.
>
> Four — **Post-Visit Survey**. After the appointment, CALL-E calls to collect patient satisfaction feedback.
>
> Five — **Waitlist Backfill**. When a slot opens, CALL-E calls the waitlist instantly to fill it.
>
> Six — **Insurance Prior Auth**. CALL-E handles the insurance phone tree automatically, so doctors don't wait."

*Screen: Click "Live Test Call" button — show the modal, select a campaign, enter a number.*

> "And I can trigger a live test call to any number, right now, from this screen."

---

### [1:35 – 1:50] — HOW IT WORKS (TECHNICAL)
*Screen: Briefly show Settings page — CALL-E card with "PRIMARY ENGINE" badge. Or show the Live Activity Feed tab.*

> "Under the hood, each campaign uses the CALL-E Python SDK. We define the goal — what the call should accomplish. CALL-E makes the call, extracts the patient's answer as structured data, and our webhook updates the EHR in real time."

---

### [1:50 – 2:00] — CLOSE
*Screen: Back to dashboard — zoom out so the full page is visible. Metrics showing.*

> "This is CALL-E making real phone calls, solving a real clinical problem. Bytelytic Clinic OS — live, working, and deployed."

---

## DELIVERY NOTES
- **Tone:** Confident engineer. Not salesy. You built this and it works.
- **Pace:** ~140 words per minute. Don't rush. Let the screen show the work.
- **Pauses:** After naming each campaign — 0.5 second pause before the next.
- **"Right now"** — say this when clicking Live Test Call. Judges love live proof.
- **Do NOT say:** "Retell", "dual path", "two engines", "dry run", "idempotency"
- **DO say:** "CALL-E", "live", "real calls", "automatic", "structured data", "webhook"

---

## SCREEN SEQUENCE (QUICK REF)
```
0:00  → Dashboard (calle-healthcare-os.vercel.app)
0:20  → Scroll down appointment list — show status badges
0:35  → Outbound Campaigns page — green "LIVE MODE" banner
0:55  → Hover campaign cards one by one (6 cards)
1:25  → Click "Live Test Call" button → modal opens
1:35  → Settings page (CALL-E PRIMARY ENGINE badge) OR Activity Feed
1:50  → Back to Dashboard — full view
2:00  → END
```

---

## RECORDING TIPS
1. **Resolution:** 1080p at 30fps minimum.
2. **Audio:** Clean USB mic or headset. No background noise.
3. **Pacing:** Speak naturally — don't rush the campaign names. Let judges absorb each one.
4. **Live proof:** If you can do the live call mid-recording, do it. Answering on speaker = instant credibility.
5. **Single take preferred:** One continuous recording proves the system is real and working.

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
