# MVP Features & Stakeholder Presentation Guide
## SleepSense — "Sleep Better, Live Better"

---

## 1. Elevator Pitch (30 seconds)

> "SleepSense is an AI-powered mobile application that monitors your sleep and snoring using just your smartphone's microphone. It detects snoring events, scores your sleep quality, identifies patterns over time, and gives you personalized, evidence-based recommendations — helping you and your doctor understand your sleep health without expensive lab equipment."

---

## 2. The Problem (Market Opportunity)

| Statistic                                          | Source           |
|---------------------------------------------------|------------------|
| 45% of adults snore regularly                     | American Academy of Sleep Medicine |
| 1 billion people have Obstructive Sleep Apnea worldwide | WHO          |
| OSA is undiagnosed in ~80% of moderate/severe cases| NIH             |
| Sleep disorders cost India ₹32,000 crore annually in lost productivity | FICCI |
| SnoreLab (competitor) has 5M+ downloads, $5/month premium | App Store |

**The Gap:** Existing solutions either require expensive medical-grade polysomnography (₹15,000+/test) or are too basic (simple decibel meters). No affordable, AI-powered, longitudinal sleep health tracker exists for the Indian market.

---

## 3. MVP Feature Set (Phase 1 — 3 months)

These are the minimum features needed to demonstrate value to stakeholders and early users:

---

### Feature 1: Sleep Recording
**What it does:** User taps "Start Recording" at bedtime. App records audio overnight using phone microphone.

**Key Details:**
- Background recording (app can be locked)
- Configurable sensitivity (filters out fan noise, AC, etc.)
- Battery optimization (records in 30s chunks, sleeps between chunks)
- Visual indicator: recording is active

**Why it matters to stakeholders:** Core value delivery — without recording, nothing else works. Demonstrates technical feasibility.

---

### Feature 2: AI-Powered Snore Detection
**What it does:** ML model (CNN on Mel spectrograms) classifies audio into snoring / breathing / silence / ambient noise.

**Key Details:**
- Classifies every 3-second window of audio
- Confidence score shown (transparent AI)
- Works offline via on-device TFLite model
- 4 sound classes clearly defined

**Why it matters to stakeholders:** This is the AI differentiator. Competitors use simple volume thresholds; we use real ML classification.

---

### Feature 3: Sleep Quality Score (0–100)
**What it does:** Computes a single, easy-to-understand score based on snoring duration, intensity, session length, and frequency.

**Key Details:**
- Grade: Excellent / Good / Fair / Poor / Critical
- Compared to previous night and 7-day average
- Calculation explained to user (transparent, builds trust)
- Color-coded (green / yellow / red)

**Why it matters to stakeholders:** A single number is compelling for users and press. Easy to demo. Drives daily engagement.

---

### Feature 4: Snoring Timeline Visualization
**What it does:** Bar/area chart showing intensity of snoring across the night in 5-minute buckets.

**Key Details:**
- X-axis: time of night
- Y-axis: snore intensity
- Color-coded by sound class
- Tap any bar to hear a sample clip of that period (audio playback)
- "Peak snoring at 2:30 AM" insight highlighted

**Why it matters to stakeholders:** Most visually impressive feature for a live demo. Immediately intuitive for any audience.

---

### Feature 5: Session History & Trends
**What it does:** List of all past sleep sessions with scores and key stats. Line chart showing quality trend over 7 / 30 / 90 days.

**Key Details:**
- Calendar heatmap view (GitHub-style, green = good nights)
- Average score this week vs. last week
- Streak tracking (nights recorded in a row)
- Export session data as CSV (for doctor visits)

**Why it matters to stakeholders:** Demonstrates retention value — users come back every day. Shows longitudinal data capability.

---

### Feature 6: Personalized Insights & Tips
**What it does:** After each session, 2–3 personalized tips generated based on detected patterns.

**Key Details:**
- Rule-based engine for MVP (no LLM dependency yet)
- 20+ evidence-based tip templates
- Categorized: positional, lifestyle, medical referral
- "Warning: 5 consecutive nights with Poor score — consider consulting a doctor"

**Why it matters to stakeholders:** Transforms raw data into actionable value. Differentiates from a simple "noise recorder."

---

### Feature 7: User Profile & Health Context
**What it does:** User inputs age, weight, sleep position, known conditions. App uses this to personalize recommendations.

**Key Details:**
- Lifestyle log (optional): alcohol, caffeine, exercise, stress
- Correlation view: "Nights you logged 2+ drinks had 35% higher snoring"
- Privacy: all data stays on device / user's account only

**Why it matters to stakeholders:** Shows that the app understands the user holistically — not just a recording tool.

---

### Feature 8: Bedtime Reminders & Goals
**What it does:** Configurable reminder to start recording. User can set a weekly sleep quality goal.

**Key Details:**
- Push notification: "Time to start tonight's recording"
- Goal: "Improve to 80+ sleep score by end of month"
- Progress bar toward goal
- Achievement badges for streaks

**Why it matters to stakeholders:** Drives DAU (Daily Active Users), a key metric investors care about.

---

## 4. MVP Non-Features (Explicitly Out of Scope)

| Feature                        | Why Deferred                                           |
|--------------------------------|--------------------------------------------------------|
| Sleep stage detection (REM/Deep)| Requires wearable data for reliable results; misleading without it |
| Apnea diagnosis                | Regulatory risk; Phase 2 with medical disclaimer       |
| Wearable integration           | WatchOS/Fitbit SDK complexity; Phase 2                 |
| Social features / sharing      | Privacy-sensitive data; user trust first               |
| Subscription payments          | Focus on user acquisition in MVP                       |
| Web dashboard                  | Mobile-first; web in Phase 2                           |

---

## 5. Phased Roadmap

### Phase 1 — MVP (Months 1–3)
Core recording, snore detection, sleep score, timeline, basic insights
**Success metric:** 500 active users, 4.0+ App Store rating

### Phase 2 — Growth (Months 4–6)
Sleep stage estimation, apnea risk screener (with disclaimer), lifestyle correlations, web dashboard, social login
**Success metric:** 5,000 active users, 20% week-1 retention

### Phase 3 — Monetization (Months 7–9)
Premium subscription (₹99/month): unlimited history, PDF reports, doctor-share feature, advanced insights, Apple Health / Google Fit integration
**Success metric:** 2% conversion to paid = sustainable revenue

### Phase 4 — Scale (Month 10+)
Wearable integration (WatchOS, Fitbit), B2B (hospital/clinic partnerships), research data platform, international expansion
**Success metric:** Series A funding readiness

---

## 6. Technical Differentiators (Stakeholder-Facing)

| Claim                          | How We Back It Up                                      |
|--------------------------------|--------------------------------------------------------|
| "AI-powered, not just a timer" | CNN on Mel spectrograms, >92% accuracy benchmark       |
| "Works offline"                | TFLite on-device model, no internet needed             |
| "Privacy-first"                | Encrypted audio, user controls deletion, no selling data|
| "Clinically correlated"        | Snore intensity correlated with dB SPL, peer-reviewed methodology |
| "Scalable to millions"         | Kubernetes, event-driven microservices, cloud-native   |

---

## 7. Demo Script (5-Minute Live Demo)

```
1. Open app → Show home screen with last night's summary (60 seconds)
   "This is what a user sees every morning — their sleep quality score,
   snoring percentage, and the key insight of the day."

2. Tap on session → Show timeline chart (60 seconds)
   "This is the snoring timeline. Each bar is 5 minutes of their night.
   You can tap any bar to hear what was recorded at that time."

3. Show trends chart (30 seconds)
   "This is their 30-day trend. You can see the improvement after they
   started sleeping on their side — a tip our AI recommended."

4. Show insights screen (30 seconds)
   "Our AI generated these three personalized recommendations based on
   7 nights of data. They're evidence-based, not generic tips."

5. Show recording screen (30 seconds)
   "Starting a new recording is this simple — one tap. The app runs in
   the background all night and the report is ready when you wake up."

6. Technical slide (60 seconds)
   "Under the hood: a CNN model running on Mel spectrograms, served
   via a microservices backend, scalable to 10,000 simultaneous users
   on day one."
```

---

## 8. Key Metrics for Stakeholder KPI Dashboard

| Metric                    | MVP Target   | Phase 2 Target |
|---------------------------|--------------|----------------|
| Total registered users    | 500          | 5,000          |
| DAU / MAU ratio           | > 30%        | > 40%          |
| Avg sessions per user/week| > 4          | > 5            |
| Session completion rate   | > 80%        | > 85%          |
| ML inference accuracy     | > 90% F1     | > 93% F1       |
| API uptime                | > 99.5%      | > 99.9%        |
| App Store rating          | > 4.0        | > 4.3          |
| User NPS score            | > 30         | > 50           |

---

## 9. Competitive Landscape

| App         | Platform | Price     | AI Detection | Sleep Stages | Our Edge           |
|-------------|----------|-----------|--------------|--------------|---------------------|
| SnoreLab    | iOS/Android| $5/mo  | Basic dB     | No           | Real ML, India-first|
| Sleep Cycle | iOS/Android| $10/mo | Accelerometer| Yes          | Snore-focused, cheaper|
| ResMed      | iOS/Android| Free   | Medical-grade| No           | No hardware needed  |
| **SleepSense**|**Both**|**Free/Freemium**|**CNN-based**|**Phase 2**|**AI + local + affordable**|

---

## 10. Investment Ask (If Pitching for Funding)

```
Seed Round Ask: ₹50 Lakhs (≈ $60,000 USD)

Allocation:
  Development (2 developers × 6 months)    ₹24 Lakhs (48%)
  Cloud infrastructure (12 months)          ₹6 Lakhs  (12%)
  ML data collection & labeling             ₹5 Lakhs  (10%)
  Marketing & user acquisition              ₹10 Lakhs (20%)
  Legal, compliance, miscellaneous          ₹5 Lakhs  (10%)

Expected outcome at 6 months:
  5,000 registered users
  500 paying subscribers at ₹99/month = ₹49,500 MRR
  Clear path to Series A at 50,000 users
```
