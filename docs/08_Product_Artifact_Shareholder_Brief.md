# SleepSense — Product Artifact
### Shareholder Brief · May 2026

---

## The Problem We Are Solving

**1 in 2 adults snores. Almost no one knows why — or how bad it really is.**

Sleep is the single most important input to human health, yet it remains the least measured. Here is what the data tells us:

| Fact | Source |
|------|--------|
| 45% of adults snore regularly | American Academy of Sleep Medicine |
| 1 billion people worldwide have Obstructive Sleep Apnea (OSA) | WHO |
| ~80% of moderate-to-severe OSA cases go undiagnosed | NIH |
| Sleep disorders cost India ₹32,000 crore annually in lost productivity | FICCI |
| A clinical sleep study (polysomnography) costs ₹15,000–₹30,000 per night | Market data |

The result is a massive silent crisis: people wake up exhausted, partners lose sleep, and the root cause — disordered nighttime breathing — goes completely undetected for years. By the time a diagnosis happens, the damage to cardiovascular health, cognitive function, and relationships is already done.

**The current options leave people stranded:**

- **Too expensive:** Clinical sleep labs charge ₹15,000+ per test, require an overnight hospital stay, and have month-long wait lists.
- **Too basic:** Apps like SnoreLab use simple decibel meters — they tell you *how loud* you snored, not *what kind* of sound it was, *when* it peaked, or *why* it's getting worse.
- **Too generic:** No solution in the Indian market combines AI-level accuracy with the affordability and longitudinal tracking that everyday users need.

**The gap SleepSense fills:** An AI-powered sleep analytics platform that works with hardware people already own — their smartphone — to give them clinical-grade insight at zero hardware cost.

---

## Why We Are Building This

### The Mission

> *Give every person on earth an honest picture of their sleep health, delivered in their pocket, every morning.*

### The Opportunity

The global sleep tech market is projected to reach **$102 billion by 2030** (CAGR ~17%). India is underserved — SnoreLab, the global market leader with 5 million downloads, does not have a meaningful India presence, charges in USD, and uses decade-old signal processing rather than machine learning.

We are building SleepSense because three things are now true simultaneously that were not true five years ago:

1. **ML is mature enough.** EfficientNet-class audio classifiers can achieve >92% accuracy on snore detection — something impossible with signal processing alone.
2. **Smartphones are powerful enough.** A TensorFlow Lite model running on-device means inference without any internet connection, protecting user privacy.
3. **The Indian middle class is ready.** 750 million smartphone users, growing health consciousness post-COVID, and a market that has shown willingness to pay for health apps.

### Why Now, Why Us

The founding team combines AI/ML engineering depth with intimate knowledge of the Indian health-tech landscape. We are not building a feature on top of someone else's platform — we are building the platform.

---

## How We Are Going to Build It

### The Product in One Sentence

SleepSense records sleep audio via the phone microphone overnight, classifies every 3 seconds of sound using a CNN neural network, generates a 0–100 Sleep Quality Score, and surfaces personalized, evidence-based recommendations each morning.

### The Technical Architecture

We are building on six microservices, each independently scalable:

```
Mobile App (React Native)
      │
      ▼
API Gateway  ──►  Auth Service       (JWT + OAuth2, Google/Apple login)
      │
      ├──────────►  Audio Ingestion   (receives 30s audio chunks → S3 storage)
      │                    │
      │               Kafka Event Bus (decouples ingestion from ML)
      │                    │
      ├──────────►  ML Inference      (CNN classifier + XGBoost intensity scorer)
      │                    │
      ├──────────►  Analytics         (aggregates into Sleep Quality Score)
      │
      ├──────────►  Insight Engine    (rule-based + LLM recommendations)
      │
      └──────────►  Notification      (FCM/APNs push, SendGrid email)
```

**What makes the architecture production-grade:**
- **30-second audio chunks** — if the phone crashes mid-session, no data is lost
- **Kafka event bus** — ML inference is fully decoupled; can retry without re-uploading audio
- **Dual inference modes** — cloud (PyTorch, highest accuracy) + on-device (TFLite, privacy mode, works offline)
- **Polyglot databases** — PostgreSQL for user data, InfluxDB for time-series snore events, Redis for caching, S3 for audio files

### The AI Models

| Model | What It Does | Accuracy Target |
|-------|-------------|----------------|
| Snore Classifier (EfficientNet-B0) | Labels every 3s window: snoring / breathing / silence / ambient | >92% F1 |
| Intensity Regressor (XGBoost) | Scores snore intensity 0–100 based on MFCCs + RMS energy | MAE <5 points |
| Sleep Stage Estimator (Phase 2) | Estimates Awake / Light / Deep / REM from audio | Phase 2 target |
| Apnea Risk Screener (Phase 2) | Flags elevated OSA risk from 7-night history | With medical disclaimer |

### The Build Roadmap

| Phase | Timeline | Milestone |
|-------|----------|-----------|
| **Phase 1 — MVP** | Months 1–3 | Recording, snore detection, sleep score, timeline chart, basic insights. Target: 500 active users, 4.0+ App Store rating |
| **Phase 2 — Growth** | Months 4–6 | Sleep stages, apnea risk screener, lifestyle correlations, web dashboard. Target: 5,000 users, 20% week-1 retention |
| **Phase 3 — Monetization** | Months 7–9 | Premium subscription ₹99/month: PDF reports, doctor-share, Apple Health / Google Fit. Target: 2% paid conversion = sustainable MRR |
| **Phase 4 — Scale** | Month 10+ | Wearable integration, B2B hospital partnerships, international expansion. Target: Series A readiness |

### The Eight MVP Features

1. **Sleep Recording** — Background microphone recording in 30s chunks, battery-optimized
2. **AI Snore Detection** — CNN classification (on-device, works offline)
3. **Sleep Quality Score (0–100)** — Single number with grade and trend comparison
4. **Snoring Timeline** — 5-minute bucket chart; tap any bar to hear the audio clip
5. **Session History & Trends** — 7/30/90-day trend, calendar heatmap, CSV export for doctors
6. **Personalized Insights** — Evidence-based recommendations (positional, lifestyle, medical referral)
7. **User Health Profile** — Age, weight, lifestyle logs; correlation view ("nights with alcohol = 35% more snoring")
8. **Bedtime Reminders & Goals** — Push notifications, weekly goal-setting, streak tracking

---

## Challenges We Are Going to Face

We are being honest with ourselves and with you about what is hard. These are the real challenges — not the polished version.

### 1. Training Data is the Bottleneck

Our CNN model needs thousands of labeled audio samples of snoring across diverse demographics, room acoustics, microphone qualities, and sleeping positions. Public datasets (ESC-50, AudioSet) exist but were not built for this use case. We need to:
- Collect and label real-world snoring audio from Indian users (different accent profiles, room noise patterns)
- Handle noisy labels (people self-reporting snoring vs. actual ground truth)
- Build a data flywheel: the more users record, the better the model gets — but we need a good model to attract users in the first place

**Mitigation:** Start with transfer learning on AudioSet (EfficientNet-B0 pre-trained weights), augment aggressively, and build a feedback loop where users can flag incorrect detections.

### 2. On-Device ML vs. Accuracy Trade-off

The TFLite model (quantized to INT8, <5MB) will be less accurate than the cloud PyTorch model. If we push users toward on-device mode for privacy, we may show them worse results. Getting this wrong risks:
- User churn if on-device results feel inaccurate
- Privacy backlash if we default to cloud-only

**Mitigation:** Be transparent. Show users which mode they are in. Offer a "privacy mode" toggle. Report confidence intervals, not just raw scores.

### 3. Battery and Background Audio on iOS

Apple aggressively restricts background audio recording. iOS's Background App Refresh has strict limits — we need to use audio session APIs in a way that keeps recording alive all night without draining the battery or being killed by the OS.

**Mitigation:** Use the `AVAudioSession` continuous recording pattern (already proven by SnoreLab and Sleep Cycle). Build a watchdog timer that detects if recording was interrupted and alerts the user in the morning.

### 4. Regulatory Risk Around Health Claims

Saying "you may have sleep apnea" is a medical claim. If we get that wrong, we face:
- User harm (false negatives: dangerous; false positives: anxiety and wasted doctor visits)
- Legal liability in India and internationally
- Potential FDA/CE classification if we expand globally

**Mitigation:** In MVP, the apnea screener is strictly out of scope. Phase 2 introduces it only with a prominent "This is not a medical diagnosis" disclaimer, validated by a sleep medicine consultant. We will not use the word "diagnose" anywhere in the product.

### 5. Microphone Variability Across Devices

A Samsung Galaxy A-series mic is not the same as an iPhone 15 Pro mic. SNR, frequency response, and directional sensitivity vary wildly. Our model must generalize across:
- Budget Android devices (₹8,000–₹15,000 range — our primary market)
- iOS (smaller but high-value segment)
- Users who sleep with the phone 1 metre away vs. on the bedside table

**Mitigation:** Calibration step during onboarding (record 10 seconds of room silence). Normalize input audio to a consistent loudness target before inference. Collect device metadata and use it as a training feature.

### 6. User Trust and Privacy

Health data is among the most sensitive categories. A single data breach or misuse allegation ends a health-tech startup. We must get this right from day one, not as an afterthought.

**Mitigation:** Audio encrypted at rest (AES-256 in S3), in transit (TLS 1.3). Users can delete all their data at any time (GDPR-compliant deletion flows). On-device mode means audio never leaves the phone. We will publish a clear, plain-English privacy policy before launch.

### 7. Retention Beyond the First Night

Sleep apps face extreme early churn. Users record one night, see a score, and forget to open the app again. Without longitudinal data, we cannot show trends — and without trends, the product loses its core value.

**Mitigation:** Bedtime reminders, streak tracking, goal-setting, and weekly email summaries are all in MVP scope. The product has to create a habit loop. Engagement metrics (DAU/MAU >30%, sessions/user/week >4) are primary KPIs — not just downloads.

### 8. Infrastructure Cost at Scale

ML inference on 30-second audio chunks is compute-intensive. At 10,000 concurrent sessions, each producing 2 chunks per minute, that is 20,000 inference requests per minute. GPU time is not free.

**Mitigation:** The Kafka buffer allows us to smooth demand spikes. Auto-scaling on Kubernetes handles burst. On-device inference (TFLite) offloads cost to the user's phone. We will profile cost-per-session before pricing the subscription.

---

## Summary

| Question | Answer |
|----------|--------|
| **What problem?** | 1 billion people have undiagnosed sleep disorders; no affordable AI-powered solution exists, especially in India |
| **Why us?** | ML expertise + India-first focus + right timing (mature models, affordable smartphones, post-COVID health awareness) |
| **How?** | 8 MVP features, microservices backend, CNN audio classifier, dual cloud+on-device inference, 12-week build to 500 users |
| **Biggest risks?** | Training data scarcity, iOS background audio limits, regulatory exposure on health claims, early user churn |

We know what we are building, we know why it matters, and we are clear-eyed about what stands in our way. SleepSense is not a "sleep timer with a nice UI" — it is a longitudinal health intelligence platform starting with the most underserved use case in consumer health: sleep.

---

*Document version: 1.0 · Prepared for stakeholder review · May 2026*
