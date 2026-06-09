# Software Requirements Specification (SRS)
## SleepSense — AI-Powered Sleep & Snoring Analytics Platform
**Version 1.0 · May 2026**

---

## Document Control

| Field | Value |
|-------|-------|
| Document ID | SRS-SLEEPSENSE-001 |
| Version | 2.0 |
| Status | Updated |
| Prepared by | SleepSense Engineering Team |
| Reviewed by | — |
| Date | May 2026 |

### Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 0.1 | May 2026 | Engineering Team | Initial draft |
| 1.0 | May 2026 | Engineering Team | Consolidated from all design docs |
| 2.0 | May 2026 | Engineering Team | Fixed 10 specification errors: Kafka topic ownership, Redis key pattern, rate-limit wording, MFCC glossary, pagination contract, Apple endpoint table entry, cross-service insight rule gap, architecture pipeline note, snoring_change definition, SAR-001 scope clarification |

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Stakeholders & User Classes](#3-stakeholders--user-classes)
4. [Functional Requirements](#4-functional-requirements)
   - 4.1 Authentication & User Management
   - 4.2 Sleep Recording
   - 4.3 AI Snore Detection
   - 4.4 Sleep Quality Score
   - 4.5 Snoring Timeline Visualization
   - 4.6 Session History & Trends
   - 4.7 Personalized Insights & Tips
   - 4.8 User Health Profile & Lifestyle Logs
   - 4.9 Bedtime Reminders & Goals
   - 4.10 Notifications
   - 4.11 Analytics API
   - 4.12 Real-time WebSocket
   - 4.13 Data Export & Privacy
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [System Architecture Requirements](#6-system-architecture-requirements)
7. [Data Requirements](#7-data-requirements)
8. [External Interface Requirements](#8-external-interface-requirements)
9. [ML / AI Requirements](#9-ml--ai-requirements)
10. [Infrastructure & Deployment Requirements](#10-infrastructure--deployment-requirements)
11. [Security Requirements](#11-security-requirements)
12. [Compliance & Legal Requirements](#12-compliance--legal-requirements)
13. [Out of Scope (Phase 1)](#13-out-of-scope-phase-1)
14. [Glossary](#14-glossary)

---

## 1. Introduction

### 1.1 Purpose

This Software Requirements Specification defines all functional and non-functional requirements for the **SleepSense** platform — Phase 1 (MVP). It serves as the primary reference for engineering, QA, design, and product teams throughout the development lifecycle.

### 1.2 Scope

SleepSense is a multi-platform, AI-driven sleep and snoring analytics application that records overnight sleep audio via smartphone microphone, classifies sounds using machine learning, scores sleep quality, and delivers personalized health recommendations.

**In scope (Phase 1):**
- iOS and Android mobile application (React Native + Expo)
- Backend microservices (Python + FastAPI)
- ML pipeline — cloud inference (PyTorch) and on-device inference (TFLite)
- REST API and WebSocket API
- PostgreSQL, InfluxDB, Redis, S3 data stores
- Kafka event bus

**Out of scope (Phase 1):** Web dashboard, sleep stage detection, apnea risk screener, wearable integration, social features, subscription payments. See Section 13.

### 1.3 Definitions and Acronyms

| Term | Definition |
|------|-----------|
| SRS | Software Requirements Specification |
| MVP | Minimum Viable Product |
| FR | Functional Requirement |
| NFR | Non-Functional Requirement |
| CNN | Convolutional Neural Network |
| MFCC | Mel-Frequency Cepstral Coefficient |
| TFLite | TensorFlow Lite (on-device ML runtime) |
| OSA | Obstructive Sleep Apnea |
| JWT | JSON Web Token |
| RBAC | Role-Based Access Control |
| HPA | Horizontal Pod Autoscaler |
| KEDA | Kubernetes Event-Driven Autoscaling |
| FCM | Firebase Cloud Messaging (Android push) |
| APNs | Apple Push Notification Service (iOS push) |
| RTO | Recovery Time Objective |
| RPO | Recovery Point Objective |
| GDPR | General Data Protection Regulation |
| SPL | Sound Pressure Level (decibels) |

### 1.4 References

| Document | Location |
|----------|----------|
| High-Level Architecture | `docs/01_High_Level_Architecture.md` |
| Low-Level Design | `docs/02_Low_Level_Design.md` |
| Database Schema | `docs/03_Database_Schema.md` |
| ML Pipeline Architecture | `docs/04_ML_Pipeline_Architecture.md` |
| API Design | `docs/05_API_Design.md` |
| Scalability & Infrastructure | `docs/06_Scalability_and_Infrastructure.md` |
| MVP Features & Stakeholder Deck | `docs/07_MVP_Features_Stakeholder_Deck.md` |

---

## 2. System Overview

### 2.1 Product Description

SleepSense allows a user to place their smartphone near their bed, tap **Start Recording**, and receive a comprehensive sleep analysis report each morning without any additional hardware.

The system:
1. Records audio in 30-second chunks throughout the night.
2. Uploads chunks to the cloud (or classifies them on-device in offline/privacy mode).
3. Runs an AI model (EfficientNet-B0 CNN) to classify every 3 seconds of audio into: *snoring / breathing / silence / ambient noise*.
4. Runs a second model (XGBoost) to score snore intensity 0–100.
5. Aggregates chunk results into a session-level Sleep Quality Score (0–100) with a letter grade.
6. Generates a visual snoring timeline and personalized recommendations.
7. Delivers the report via push notification when the user wakes up.

### 2.2 System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL ACTORS                             │
│  User (Sleeper)   Google/Apple OAuth   FCM/APNs   SendGrid Email    │
└──────────┬──────────────────────────────────────────────────────────┘
           │ HTTPS / WSS
┌──────────▼──────────────────────────────────────────────────────────┐
│                    SLEEPSENSE PLATFORM                                │
│                                                                      │
│  Mobile App (iOS/Android)  ─►  API Gateway  ─►  Microservices      │
│                                                        │             │
│                                              ┌─────────▼─────────┐  │
│                                              │  Data Layer       │  │
│                                              │  PostgreSQL       │  │
│                                              │  InfluxDB         │  │
│                                              │  Redis            │  │
│                                              │  S3 / MinIO       │  │
│                                              │  Kafka            │  │
│                                              └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.3 Microservices Overview

| Service | Responsibility |
|---------|---------------|
| Auth Service | Registration, login, JWT, OAuth2 (Google/Apple) |
| Audio Ingestion Service | Receive audio chunks → S3 → emit Kafka events |
| ML Inference Service | Kafka consumer → CNN + XGBoost → InfluxDB |
| Analytics Service | Aggregate chunk results → Sleep Quality Score → PostgreSQL |
| Insight Engine | Rule-based recommendations from session + history |
| Notification Service | FCM/APNs push, SendGrid email, in-app alerts |

---

## 3. Stakeholders & User Classes

### 3.1 Primary Users

| User Class | Description | Primary Goals |
|-----------|-------------|---------------|
| Regular Sleeper | Adult who snores or suspects poor sleep | Track nightly sleep quality, see trends, get actionable tips |
| Partner Reporter | Bed partner who reports snoring | Start recording on behalf of the sleeper |
| Health-Conscious User | User managing weight, alcohol, stress | Correlate lifestyle choices with sleep quality |

### 3.2 Secondary Stakeholders

| Stakeholder | Interest |
|------------|---------|
| Product Owner / Founders | Feature completeness, KPI targets |
| Engineering Team | Technical clarity, buildable specifications |
| ML Team | Model accuracy targets, data pipeline |
| DevOps Team | Infrastructure, SLAs |
| Legal / Compliance | GDPR, health claim boundaries |
| Investors | Roadmap, metrics, monetization readiness |

### 3.3 User Characteristics

- **Platform:** Primarily Android (budget devices ₹8,000–₹25,000 range); secondarily iOS.
- **Connectivity:** Mixed — urban WiFi, rural mobile data; on-device fallback required.
- **Technical literacy:** Low to medium; UI must be single-tap to start recording.
- **Health context:** Non-clinical users. Must not be presented with diagnostic claims.

---

## 4. Functional Requirements

Requirements use MoSCoW prioritization:
- **M** — Must have (MVP blocker)
- **S** — Should have (strongly preferred for MVP)
- **C** — Could have (nice to have)
- **W** — Won't have (Phase 2+)

---

### 4.1 Authentication & User Management

#### FR-AUTH-001 — Email Registration
**Priority:** M
**Description:** A new user can create an account with email, password, and display name.
**Acceptance Criteria:**
- System validates email format and uniqueness.
- Password must be minimum 8 characters, contain at least one uppercase, one number, one special character.
- Password stored as bcrypt hash; plaintext never persisted.
- On success, returns access token (15-min TTL) and refresh token (30-day TTL).
- On duplicate email: returns HTTP 409 with RFC 7807 error body.
- Account starts with `is_verified = false`; verification email sent via SendGrid.

#### FR-AUTH-002 — Email/Password Login
**Priority:** M
**Description:** Registered user logs in with email and password.
**Acceptance Criteria:**
- Returns `access_token`, `refresh_token`, `expires_in: 900` on success.
- Failed login returns HTTP 401 with a **generic** message (no user enumeration).
- After 10 attempts (successful or not) within 15 minutes from the same IP, endpoint returns HTTP 429 (Too Many Requests) for the remainder of the 15-minute window. All attempts are counted — counting only failures would allow user enumeration via timing differences.
- Rate limit key stored in Redis: `ratelimit:login:{ip_address}`, TTL 15 minutes.

#### FR-AUTH-003 — Token Refresh
**Priority:** M
**Description:** Client exchanges a valid refresh token for a new access token.
**Acceptance Criteria:**
- Returns new `access_token` with 15-min TTL.
- Refresh token is **rotated on each use** (old token invalidated in Redis).
- Expired or already-used refresh token returns HTTP 401.

#### FR-AUTH-004 — Logout
**Priority:** M
**Description:** User can log out, invalidating the refresh token.
**Acceptance Criteria:**
- Refresh token removed from Redis.
- All subsequent requests with the old refresh token return HTTP 401.

#### FR-AUTH-005 — Google OAuth2 Login
**Priority:** S
**Description:** User can sign in via Google account.
**Acceptance Criteria:**
- App initiates OAuth2 flow; server validates Google ID token.
- On first sign-in: creates user account with `password_hash = NULL`.
- Social account record created in `social_accounts` table (`provider = 'google'`).
- Returns same token structure as email login.

#### FR-AUTH-006 — Apple Sign-In
**Priority:** S
**Description:** User can sign in via Apple account (required for iOS App Store compliance).
**Acceptance Criteria:**
- Server validates Apple identity token.
- Handles Apple's email relay (private relay emails stored, not user's real email).
- Same token structure returned as email login.

#### FR-AUTH-007 — Password Reset
**Priority:** S
**Description:** User can reset a forgotten password via email link.
**Acceptance Criteria:**
- `POST /auth/forgot-password` sends a time-limited reset link (TTL: 1 hour) via SendGrid.
- `POST /auth/reset-password` accepts the token + new password.
- After successful reset, all existing refresh tokens for the user are revoked.

#### FR-AUTH-008 — User Profile CRUD
**Priority:** M
**Description:** Authenticated user can view and update their profile.
**Acceptance Criteria:**
- `GET /users/me` returns: id, email, display_name, date_of_birth, gender, weight_kg, height_cm, timezone, profile_image URL, created_at.
- `PATCH /users/me` accepts partial updates (only provided fields changed).
- Timezone stored as IANA string (e.g., `Asia/Kolkata`).
- Profile image upload: multipart form to `/users/me/avatar`; stored in S3 at `profiles/{user_id}/avatar.jpg`; CDN URL returned.

---

### 4.2 Sleep Recording

#### FR-REC-001 — Start Recording Session
**Priority:** M
**Description:** User initiates a new sleep recording session.
**Acceptance Criteria:**
- `POST /sessions` creates a new session record with `status = 'recording'`.
- Returns `session_id` (UUID) and a short-lived `upload_token` for chunk uploads.
- Only one active session allowed per user at a time; starting a second returns HTTP 409.
- Session stored in PostgreSQL `sleep_sessions` table.

#### FR-REC-002 — Audio Chunk Upload
**Priority:** M
**Description:** Mobile app uploads 30-second audio chunks continuously throughout the night.
**Acceptance Criteria:**
- Endpoint: `POST /sessions/{session_id}/chunks` — `multipart/form-data`.
- Fields: `chunk_index` (integer, 0-based, sequential), `duration_seconds` (integer), `audio` (binary file).
- Accepted MIME types: `audio/opus`, `audio/wav`, `audio/m4a`.
- Maximum file size per chunk: 10 MB.
- Server validates: session exists, belongs to authenticated user, `chunk_index` is sequential (no gaps).
- Audio stored in S3: `s3://sleepsense-audio-{env}/{user_id}/{session_id}/chunk_{chunk_index:03d}.opus`.
- Metadata inserted into `audio_chunks` table: `chunk_id`, `session_id`, `s3_key`, `duration_seconds`, `file_size_bytes`, `status = 'pending'`.
- Kafka message published to topic `audio.chunk.uploaded` with: `chunk_id`, `session_id`, `user_id`, `s3_key`, `chunk_index`, `duration_seconds`, `timestamp`.
- Returns HTTP 202 Accepted: `{chunk_id, chunk_index, status: "queued"}`.
- Rate limit: 120 chunk uploads per hour per user.

> **Implementation note (current build):** The sample build uses a simplified JSON-only upload path where the mobile app sends pre-analyzed stats (`chunk_index`, `avg_intensity`, `dominant_class`, `snore_event_count`) as a JSON body to the Analytics Service directly, bypassing the Audio Ingestion → S3 → Kafka → ML Inference pipeline. No raw audio is stored in this mode. The full binary upload pipeline described above is the production target.

#### FR-REC-003 — Background Recording on Mobile
**Priority:** M
**Description:** App must continue recording with screen locked and app backgrounded.
**Acceptance Criteria:**
- iOS: uses `AVAudioSession` with `.playAndRecord` category; `AVAudioSessionCategoryOptionAllowBluetooth` enabled.
- Android: uses a Foreground Service with `RECORD_AUDIO` permission; persistent notification shown while recording.
- Recording must survive screen lock, incoming calls (brief pause + resume), and app being backgrounded.
- If recording is interrupted (OS kills service), app detects interruption on next open and alerts user that the session may be incomplete.
- Battery optimization: encode audio to Opus (compressed) before upload to reduce network usage; use `requestIdleCallback`-equivalent patterns between chunks.

#### FR-REC-004 — End Session
**Priority:** M
**Description:** User ends the sleep recording in the morning.
**Acceptance Criteria:**
- `POST /sessions/{session_id}/end` accepts: `ended_at` (ISO 8601), optional `notes` (text), optional `room_temperature` (decimal).
- Session `status` updated to `'processing'`.
- Analytics Service is triggered (via Kafka event `session.ended`) to compute the final session summary.
- Response: `{session_id, status: "processing", estimated_ready_in_seconds: 120}`.

#### FR-REC-005 — Session Status Polling
**Priority:** M
**Description:** Client can check if session analysis is complete.
**Acceptance Criteria:**
- `GET /sessions/{session_id}/status` returns: `{status, processed_chunks, total_chunks, percent_complete}`.
- Status values: `recording` → `processing` → `complete` | `failed`.
- Status cached in Redis: `session:status:{session_id}`, TTL 24 hours.

---

### 4.3 AI Snore Detection

#### FR-ML-001 — Audio Preprocessing
**Priority:** M
**Description:** Each uploaded chunk is preprocessed into a standard format before inference.
**Acceptance Criteria:**
- Decode Opus/WAV/M4A → PCM float32.
- Resample to 16 kHz mono.
- Normalize amplitude (peak normalization to 0 dBFS).
- Remove DC offset.
- Trim silence below -40 dBFS threshold.
- Segment into 3-second windows with 50% overlap.
- Compute Mel spectrogram per window: n_mels=128, hop_length=512, n_fft=2048, normalize to [-1, 1].

#### FR-ML-002 — Snore Classification
**Priority:** M
**Description:** CNN model classifies every 3-second window of audio into one of four sound classes.
**Acceptance Criteria:**
- Model architecture: EfficientNet-B0 fine-tuned on AudioSet.
- Input: (1, 128, 128) Mel spectrogram tensor.
- Output: softmax probability distribution over 4 classes: `{snoring, breathing, silence, ambient}`.
- Class with highest probability is the `dominant_class` for that window.
- Confidence score (max probability) stored alongside classification.
- Model accuracy target: F1 score > 92% on held-out test set.
- Inference latency target: < 50 ms per 3-second window on CPU.

#### FR-ML-003 — Snore Intensity Regression
**Priority:** M
**Description:** For windows classified as snoring, compute an intensity score 0–100.
**Acceptance Criteria:**
- Model: XGBoost Gradient Boosted Trees.
- Input features: 40 MFCC coefficients + delta MFCCs + delta-delta MFCCs + RMS energy + zero-crossing rate + spectral centroid + spectral rolloff + pitch (F0) + Formant F1.
- Output: float in range [0.0, 100.0] correlated with dB SPL measurements.
- MAE target: < 5 intensity points on validation set.
- Only runs on windows where CNN dominant_class == `snoring`.

#### FR-ML-004 — Chunk-Level Result Aggregation
**Priority:** M
**Description:** Per-window results are aggregated into a single chunk-level summary.
**Acceptance Criteria:**
- Aggregate fields: `snore_windows` (count), `total_windows` (count), `snore_ratio` (float 0–1), `avg_intensity` (float), `max_intensity` (float).
- Per-event array: `[{start_sec, end_sec, class, intensity, confidence}]`.
- Results written to:
  - InfluxDB measurement `snore_events` (per-window, timestamped).
  - PostgreSQL `audio_chunks.analysis_result` (JSONB, chunk-level summary).
- Kafka event published: `analysis.complete` with `{session_id, chunk_id, summary}`.
- `audio_chunks.status` updated to `'done'`; `processed_at` timestamp set.

#### FR-ML-005 — On-Device TFLite Inference
**Priority:** S
**Description:** App can run snore classification locally without internet connection.
**Acceptance Criteria:**
- TFLite model: INT8 quantized EfficientNet-B0, max 5 MB, bundled with app.
- Activated automatically when: no internet connection detected, OR user enables "Privacy Mode" toggle.
- On-device accuracy: ≥ 90% of full-precision cloud model (verified during model export pipeline).
- Inference latency: < 100 ms per 3-second window on ARM Cortex-A55 (mid-range Android).
- When in on-device mode: audio is NOT uploaded to S3; only aggregated results (no raw audio) sent to analytics endpoint after session ends.
- UI shows a "Privacy Mode Active" indicator during recording.

---

### 4.4 Sleep Quality Score

#### FR-SCORE-001 — Sleep Quality Score Computation
**Priority:** M
**Description:** After a session ends, a single 0–100 Sleep Quality Score is computed for the night.
**Acceptance Criteria:**
- Formula:
  ```
  Score = 100 − (
    snore_ratio × 40
    + (avg_intensity / 100) × 25
    + interruption_count × 2
    + session_gap_penalty        [up to 15 if session < 6 hours]
  )
  Clamped to [0, 100]
  ```
- Grade mapping:
  - 90–100 → Excellent
  - 75–89  → Good
  - 60–74  → Fair
  - 40–59  → Poor
  - 0–39   → Critical
- Score and grade stored in `sleep_sessions.sleep_quality_score` and `sleep_sessions.sleep_quality_grade`.
- Score displayed in the app dashboard with color coding: green (Good/Excellent), yellow (Fair), red (Poor/Critical).

#### FR-SCORE-002 — Score Explanation
**Priority:** S
**Description:** User can see what factors contributed to their score.
**Acceptance Criteria:**
- Dashboard shows a breakdown: snoring impact, intensity penalty, interruption penalty, duration penalty.
- Shown as a simple bar or pie breakdown, not raw formula numbers.
- Explanation text: e.g., "Snoring for 28% of the night reduced your score by 11 points."

---

### 4.5 Snoring Timeline Visualization

#### FR-VIS-001 — 5-Minute Bucket Timeline
**Priority:** M
**Description:** Session detail screen shows a chart of snoring intensity across the night in 5-minute buckets.
**Acceptance Criteria:**
- Data source: InfluxDB `session_metrics` measurement, aggregated into 5-minute windows.
- X-axis: time of night (start → end).
- Y-axis: average snore intensity (0–100).
- Each bucket is color-coded: blue (silence/breathing), yellow (ambient), orange (light snoring), red (heavy snoring).
- API endpoint: `GET /analytics/timeline/{session_id}` returns array of bucket objects: `{timestamp, avg_intensity, dominant_class, snore_event_count}`.
- Bucket with highest intensity is highlighted with an annotation: "Peak snoring at 2:30 AM".

#### FR-VIS-002 — Audio Playback from Timeline
**Priority:** S
**Description:** User can tap any bar on the timeline to hear a short audio clip from that time period.
**Acceptance Criteria:**
- Tapping a bar triggers playback of the corresponding audio chunk from S3.
- Generates a pre-signed S3 URL (TTL: 15 minutes) for streaming.
- Playback limited to 30 seconds per tap.
- Available only if session was recorded in cloud mode (not on-device privacy mode).

---

### 4.6 Session History & Trends

#### FR-HIST-001 — Session List
**Priority:** M
**Description:** User can view a paginated list of all past sleep sessions.
**Acceptance Criteria:**
- Endpoint: `GET /sessions?cursor=<token>&limit=20&from=<date>&to=<date>`.
- Each item: `{id, started_at, duration_minutes, sleep_quality_score, sleep_quality_grade, snoring_percentage}`.
- Cursor-based pagination: response includes `{sessions, next_cursor, has_more}`. `next_cursor` is an opaque token encoding the last returned `started_at` + `id`. No `total_count` field — total counts are incompatible with cursor pagination and require a full-table scan.
- Date range filter (`from`, `to`) supported; both are optional ISO 8601 dates.

#### FR-HIST-002 — Trend Chart (7 / 30 / 90 Days)
**Priority:** M
**Description:** Dashboard shows a line chart of sleep quality scores over time.
**Acceptance Criteria:**
- Endpoint: `GET /analytics/trends?period=7d|30d|90d`.
- Returns array of `{date, quality_score, snoring_percentage, duration_minutes}` — one per recorded night.
- Summary: `{avg_quality_score, avg_snoring_percentage, trend_direction: 'improving'|'declining'|'stable', trend_change_percent, nights_recorded, nights_missed}`.
- Trend direction computed by comparing latest 7-day average against prior 7-day average.

#### FR-HIST-003 — Calendar Heatmap
**Priority:** S
**Description:** Sessions are shown as a GitHub-style calendar heatmap.
**Acceptance Criteria:**
- Each day cell is colored based on quality score: dark green (Excellent) → light green (Good) → yellow (Fair) → red (Poor/Critical) → grey (no recording).
- Tapping a cell navigates to that session's detail screen.
- Shows last 90 days by default.

#### FR-HIST-004 — Streak Tracking
**Priority:** S
**Description:** User sees how many consecutive nights they have recorded.
**Acceptance Criteria:**
- Current streak computed as: number of consecutive calendar days ending today where a completed session exists.
- Longest streak also displayed.
- Shown on the dashboard home screen.

#### FR-HIST-005 — Weekly Summary
**Priority:** S
**Description:** A summary card for the current week is shown on the dashboard.
**Acceptance Criteria:**
- Endpoint: `GET /analytics/weekly-summary`.
- Returns: `{week_start, week_end, nights_recorded, avg_quality_score, avg_snoring_percentage, avg_sleep_duration_minutes, best_night: {date, score}, worst_night: {date, score}, vs_previous_week: {quality_change, snoring_change}}`.
- `quality_change`: current week `avg_quality_score` minus previous week `avg_quality_score` (positive = improving).
- `snoring_change`: current week `avg_snoring_percentage` minus previous week `avg_snoring_percentage` in percentage points (positive = more snoring, negative = less snoring).
- Shows week-over-week delta with up/down arrow and percentage.

#### FR-HIST-006 — CSV Export
**Priority:** S
**Description:** User can export session data as a CSV file for doctor visits.
**Acceptance Criteria:**
- `GET /sessions/export?format=csv&from=<date>&to=<date>` returns a downloadable CSV.
- Columns: date, start_time, end_time, duration_hours, quality_score, quality_grade, snoring_percentage, snoring_duration_min, avg_intensity, max_intensity, snore_events_per_hour.
- Download link is pre-signed and expires in 1 hour.

---

### 4.7 Personalized Insights & Tips

#### FR-INS-001 — Rule-Based Insight Generation
**Priority:** M
**Description:** After each session, 2–3 personalized tips are generated based on detected patterns.
**Acceptance Criteria:**
- Insight engine applies 5 core rules (evaluated in priority order):
  1. **POSITIONAL_SNORING:** If peak snoring correlates with back-sleeping (via user's declared sleep position) → suggest side-sleeping. The Insight Engine must fetch `sleep_position` from the Auth Service via `GET /users/{user_id}/health-profile` (internal service-to-service call); direct DB access is forbidden per SAR-004.
  2. **ALCOHOL_CORRELATION:** If user logged alcohol AND snore_score > 70 same night → show alcohol-snoring link.
  3. **CHRONIC_SNORING:** If snore_score > 60 for 5+ consecutive nights → suggest consulting a sleep specialist.
  4. **IMPROVEMENT_TREND:** If average score improved > 15 points over 7 days → positive reinforcement.
  5. **SLEEP_DEBT:** If average sleep duration < 6 hours over 5 days → suggest sleep hygiene.
- Tips library: minimum 20 evidence-based templates, categorized as: positional, lifestyle, medical referral.
- Insights stored in `session_insights` table: `{insight_type, priority, title, body, action_url}`.

#### FR-INS-002 — Insight Display
**Priority:** M
**Description:** User sees their insights on the morning dashboard.
**Acceptance Criteria:**
- Endpoint: `GET /insights?session_id=<uuid>` returns up to 3 highest-priority insights for a session.
- Insight types: `tip` (blue), `warning` (yellow), `achievement` (green).
- User can mark insights as read: `PATCH /insights/{id}/read`.
- `is_read` flag updated in database.
- Action URL is a deep link (e.g., `sleepsense://tips/positional-snoring`) — tapping opens an in-app article.

---

### 4.8 User Health Profile & Lifestyle Logs

#### FR-PROFILE-001 — Health Profile
**Priority:** S
**Description:** User can input health context to improve recommendation personalization.
**Acceptance Criteria:**
- `GET /users/me/health-profile` and `PUT /users/me/health-profile`.
- Fields: `sleep_position` (back/side/stomach), `known_conditions` (text array), `medications` (text array), `alcohol_frequency` (never/occasionally/regularly), `smoking_status` (never/former/current), `cpap_user` (boolean), `snoring_severity_self` (1–5 integer).
- All fields optional; stored in `user_health_profile` table.
- Health profile data used by Insight Engine for rule matching.

#### FR-PROFILE-002 — Lifestyle Log Entry
**Priority:** S
**Description:** User can log daily lifestyle factors.
**Acceptance Criteria:**
- `POST /lifestyle-logs` accepts: `logged_date` (date), `alcohol_units` (decimal), `exercise_minutes` (integer), `stress_level` (1–5), `caffeine_cups` (integer), `sleep_aid_used` (boolean), optional `notes`.
- Only one log allowed per user per date (UNIQUE constraint); subsequent POST on same date updates the record.
- `GET /lifestyle-logs?from=<date>&to=<date>` returns all logs in the range.

#### FR-PROFILE-003 — Lifestyle Correlation View
**Priority:** C
**Description:** User sees correlations between lifestyle factors and sleep quality.
**Acceptance Criteria:**
- Dashboard card: "Nights you logged 2+ alcohol units had 35% higher snoring on average."
- Computed by Analytics Service by joining `lifestyle_logs` and `sleep_sessions` by date.
- Requires minimum 5 data points to show a correlation (avoids spurious results).
- Updated after each new session completes.

---

### 4.9 Bedtime Reminders & Goals

#### FR-GOAL-001 — Bedtime Reminder
**Priority:** S
**Description:** User can configure a push notification reminder to start recording.
**Acceptance Criteria:**
- User sets a reminder time (e.g., 10:30 PM) in notification settings.
- Reminder stored in `user_goals` or notification preferences.
- Push notification sent nightly at configured time: "Time to start tonight's recording."
- User can disable the reminder.

#### FR-GOAL-002 — Sleep Quality Goal
**Priority:** S
**Description:** User can set a target sleep quality score with a deadline.
**Acceptance Criteria:**
- `goal_type = 'quality_score'`, `target_value = 80`, `target_date = <date>`.
- Progress bar on dashboard showing current 7-day average vs. target.
- When `current_value >= target_value`, goal is marked `is_achieved = true`.

#### FR-GOAL-003 — Recording Streak Goal
**Priority:** C
**Description:** User can set a target number of consecutive recording nights.
**Acceptance Criteria:**
- `goal_type = 'recording_streak'`, `target_value = 7` (record 7 nights in a row).
- Progress updated daily.
- Achievement badge unlocked when goal is reached.

---

### 4.10 Notifications

#### FR-NOTIF-001 — Sleep Report Ready
**Priority:** M
**Description:** User is notified when overnight session analysis is complete.
**Acceptance Criteria:**
- Push notification sent via FCM (Android) / APNs (iOS) when `session.status = 'complete'`.
- Notification title: "Your sleep report is ready."
- Body: "Sleep score: 72 (Fair) · Snoring: 17% of the night."
- Deep link to session detail screen.
- Fallback: if push fails, in-app notification shown on next app open.

#### FR-NOTIF-002 — Weekly Summary Notification
**Priority:** S
**Description:** User receives a weekly summary every Monday morning.
**Acceptance Criteria:**
- Scheduled job runs weekly (Apache Airflow or cron).
- Email sent via SendGrid: weekly averages, best/worst night, trend.
- Push notification: "Your weekly sleep report is ready."

#### FR-NOTIF-003 — Health Alert
**Priority:** S
**Description:** User is alerted when chronic poor sleep patterns are detected.
**Acceptance Criteria:**
- Triggered when CHRONIC_SNORING rule fires (5+ consecutive nights with score < 60).
- Notification: "5 consecutive nights of poor sleep detected. Consider consulting a doctor."
- Not classified as a medical diagnosis — wellness alert only.
- Maximum 1 health alert per 7-day period (no spam).

#### FR-NOTIF-004 — Achievement Badge Notification
**Priority:** C
**Description:** User is notified when they achieve a goal or streak.
**Acceptance Criteria:**
- Triggered when `user_goals.is_achieved` is set to true.
- Push notification with badge icon and congratulatory message.

---

### 4.11 Analytics API

#### FR-API-001 — Session Detail
**Priority:** M
**Description:** Full session analysis results available via API.
**Acceptance Criteria:**
- `GET /sessions/{session_id}` returns all computed fields when `status = 'complete'`:
  - `started_at`, `ended_at`, `duration_minutes`
  - `sleep_quality_score`, `sleep_quality_grade`
  - `snoring_duration_min`, `snoring_percentage`, `snore_events_per_hour`
  - `avg_snore_intensity`, `max_snore_intensity`
  - `peak_snoring_hour` (hour of night, 0–23)
  - `total_chunks`, `processed_chunks`
- Returns 202 with progress if `status = 'processing'`.

---

### 4.12 Real-Time WebSocket

#### FR-WS-001 — WebSocket Connection
**Priority:** S
**Description:** Client maintains a WebSocket connection during active recording for real-time feedback.
**Acceptance Criteria:**
- Connection: `WSS wss://api.sleepsense.app/v1/ws?token=<access_token>`.
- JWT validated on connection; invalid token closes connection with code 1008.
- Heartbeat/ping-pong every 30 seconds to keep connection alive.

#### FR-WS-002 — Real-Time Chunk Analysis Events
**Priority:** S
**Description:** Server pushes chunk analysis results to the app in real time.
**Acceptance Criteria:**
- After each chunk is analyzed, server pushes `chunk.analyzed` event:
  ```json
  {
    "event": "chunk.analyzed",
    "data": {
      "session_id": "uuid",
      "chunk_index": 5,
      "dominant_class": "snoring",
      "intensity": 71.2,
      "processed_chunks": 6,
      "total_chunks": 6
    }
  }
  ```
- App uses this to show a real-time "snoring now" indicator on the recording screen.

#### FR-WS-003 — Session Complete Event
**Priority:** S
**Description:** Server notifies client when the full session analysis is complete.
**Acceptance Criteria:**
- Server pushes `session.complete` event:
  ```json
  { "event": "session.complete", "data": { "session_id": "uuid", "sleep_quality_score": 72.4, "summary_available": true } }
  ```
- Client navigates to session detail screen on receiving this event.

---

### 4.13 Data Export & Privacy

#### FR-PRIV-001 — User Data Deletion
**Priority:** M
**Description:** User can delete their account and all associated data.
**Acceptance Criteria:**
- `DELETE /users/me` triggers GDPR-compliant deletion flow.
- Cascade delete: all rows in `sleep_sessions`, `audio_chunks`, `lifestyle_logs`, `user_goals`, `session_insights`, `notifications`, `social_accounts`, `user_health_profile`.
- Audio files deleted from S3.
- InfluxDB events: `user_id` tag removed (anonymized); aggregated data retained for research only if user previously consented.
- Deletion completed within 30 days (GDPR requirement); user receives email confirmation.
- Refresh tokens revoked immediately.

#### FR-PRIV-002 — Per-Session Audio Deletion
**Priority:** S
**Description:** User can delete audio files for a specific session without deleting the session summary.
**Acceptance Criteria:**
- `DELETE /sessions/{session_id}/audio` removes all S3 objects for that session.
- Session summary (score, timeline, insights) retained in PostgreSQL and InfluxDB.
- `audio_chunks.s3_key` set to NULL after deletion.

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-PERF-001 | API response latency (P95) | < 200 ms |
| NFR-PERF-002 | ML inference time per 30-second audio chunk | < 3 seconds |
| NFR-PERF-003 | CNN inference per 3-second window (cloud, CPU) | < 50 ms |
| NFR-PERF-004 | TFLite inference per 3-second window (on-device, ARM Cortex-A55) | < 100 ms |
| NFR-PERF-005 | Session analysis end-to-end latency (chunk upload → report ready) | < 5 minutes after session end |
| NFR-PERF-006 | Audio upload throughput per chunk (30s Opus) | < 5 seconds on 4G connection |
| NFR-PERF-007 | Session list query latency | < 100 ms with index on (user_id, started_at DESC) |
| NFR-PERF-008 | InfluxDB timeline query for 8-hour session | < 500 ms |

### 5.2 Scalability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-SCALE-001 | Concurrent active recording sessions | 10,000 simultaneous (v1 target) |
| NFR-SCALE-002 | Kafka message throughput | 20,000 audio chunk events per minute at peak |
| NFR-SCALE-003 | ML inference pod auto-scaling | 2 → 8 GPU replicas based on Kafka consumer lag |
| NFR-SCALE-004 | Audio ingestion pod auto-scaling | 2 → 10 replicas based on CPU utilization > 70% |
| NFR-SCALE-005 | S3 storage growth | Infinite (S3 by design); estimated 50 MB per 8-hour session |

### 5.3 Availability & Reliability

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-AVAIL-001 | Overall system uptime SLA | 99.9% (≤ 8.7 hours downtime/year) |
| NFR-AVAIL-002 | RTO for P1 incidents | < 1 hour |
| NFR-AVAIL-003 | RPO (maximum data loss) | < 5 minutes |
| NFR-AVAIL-004 | Audio chunk loss tolerance | Zero — S3 stores chunk before Kafka event is emitted |
| NFR-AVAIL-005 | ML inference retry | Kafka enables automatic retry if ML service is temporarily down |
| NFR-AVAIL-006 | Database availability | Multi-AZ PostgreSQL; automatic failover < 60 seconds |

### 5.4 Mobile-Specific

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-MOB-001 | App size (initial download) | < 50 MB (including TFLite model) |
| NFR-MOB-002 | Battery drain during overnight recording | < 20% of battery per 8-hour session on mid-range device |
| NFR-MOB-003 | Background recording survival | Must survive screen lock, incoming calls, app backgrounding |
| NFR-MOB-004 | Minimum supported iOS version | iOS 15+ |
| NFR-MOB-005 | Minimum supported Android version | Android 10 (API level 29)+ |
| NFR-MOB-006 | Supported screen sizes | Phones from 5" to 7"; tablets not required for MVP |

### 5.5 Storage

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-STOR-001 | Raw audio storage per session | ~50 MB for 8-hour session (Opus-compressed) |
| NFR-STOR-002 | Data retention — raw audio files | 12 months; user can delete any time |
| NFR-STOR-003 | Data retention — snore event metrics (InfluxDB) | 24 months |
| NFR-STOR-004 | Data retention — session summaries (PostgreSQL) | Indefinite (until account deletion) |
| NFR-STOR-005 | Data retention — insights | 6 months (background purge job) |
| NFR-STOR-006 | Data retention — notification logs | 90 days (rolling purge) |

---

## 6. System Architecture Requirements

### 6.1 Microservice Architecture

| ID | Requirement |
|----|-------------|
| SAR-001 | Each microservice targets a 5-layer internal pattern: API Routes → Service Layer → Repository Layer → Domain Layer → Infrastructure Layer. The current sample build uses a simplified 2-layer layout (Routes → Models) and will be refactored to the full 5-layer pattern as services mature. New services must be built to the 5-layer target from the start. |
| SAR-002 | All services expose health check endpoints: `GET /health` (liveness) and `GET /ready` (readiness). |
| SAR-003 | Inter-service communication: REST (synchronous, user-facing) + Apache Kafka (asynchronous, ML pipeline). |
| SAR-004 | No direct database sharing between services. Each service owns its data; cross-service reads go via API. |
| SAR-005 | All services containerized with Docker; deployed on Kubernetes (EKS). |

### 6.2 Kafka Topics

| Topic | Producer | Consumer | Description |
|-------|----------|----------|-------------|
| `audio.chunk.uploaded` | Audio Ingestion | ML Inference | New chunk ready for analysis |
| `analysis.complete` | ML Inference | Analytics | Chunk analysis results |
| `session.ended` | Analytics | Insight Engine, Notification | Session finalized (emitted by Analytics when `POST /sessions/{id}/end` is called; Audio Ingestion is not involved in session lifecycle) |
| `insights.generate` | Analytics | Insight Engine | Trigger insight generation |
| `notification.send` | Insight Engine, Analytics | Notification Service | Trigger push/email |

### 6.3 API Gateway Requirements

| ID | Requirement |
|----|-------------|
| SAR-006 | All external traffic routes through API Gateway (Kong / Nginx). |
| SAR-007 | API Gateway handles: JWT validation, rate limiting, SSL termination, request routing, CORS, logging. |
| SAR-008 | WebSocket connections route through a dedicated WebSocket Gateway (separate from REST gateway). |
| SAR-009 | CloudFlare sits in front of the load balancer for DDoS protection, WAF, and CDN caching. |

---

## 7. Data Requirements

### 7.1 PostgreSQL Tables (Core)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `users` | User accounts | id (UUID PK), email (unique), password_hash, display_name, date_of_birth, gender, weight_kg, height_cm, timezone, is_active, is_verified |
| `social_accounts` | OAuth2 provider links | user_id (FK), provider, provider_uid |
| `user_health_profile` | Health context | user_id (FK unique), sleep_position, known_conditions (text[]), medications (text[]), cpap_user |
| `sleep_sessions` | Sleep recording sessions | id, user_id (FK), started_at, ended_at, status, sleep_quality_score, sleep_quality_grade, snoring stats, total_chunks, processed_chunks |
| `audio_chunks` | Per-chunk metadata | id, session_id (FK), chunk_index, s3_key, duration_seconds, status, analysis_result (JSONB) |
| `session_insights` | Generated tips/warnings | id, session_id (FK), user_id (FK), insight_type, priority, title, body, action_url, is_read |
| `weekly_summaries` | Aggregated weekly stats | user_id (FK), week_start, week_end, avg_quality_score, trend_direction |
| `lifestyle_logs` | Daily lifestyle factors | user_id (FK), logged_date, alcohol_units, exercise_minutes, stress_level, caffeine_cups |
| `user_goals` | User-set sleep goals | user_id (FK), goal_type, target_value, current_value, is_achieved, target_date |
| `notifications` | Notification log | user_id (FK), type, title, body, payload, channel, sent_at, is_read |

### 7.2 InfluxDB Measurements

| Measurement | Tags | Fields | Granularity |
|-------------|------|--------|-------------|
| `snore_events` | session_id, user_id, event_class | intensity (float), confidence (float), chunk_index (int), window_index (int) | Per 3-second window |
| `session_metrics` | session_id, user_id | avg_intensity (float), snore_event_count (int), dominant_class (string), decibel_estimate (float) | 5-minute aggregated buckets |

### 7.3 Redis Keys

| Key Pattern | Value | TTL | Purpose |
|-------------|-------|-----|---------|
| `rt:{token}` | `user_id` (string) | 30 days | Refresh token store — keyed by the token itself for O(1) lookup and rotation; old token is deleted on use (rotation). If per-device revocation is required in future, migrate to `rt:{user_id}:{device_id}:{token_hash}`. |
| `ratelimit:login:{ip_address}` | Integer counter | 15 minutes | Login rate limiting |
| `session:status:{session_id}` | JSON {status, processed_chunks, total_chunks, last_updated} | 24 hours | Session processing cache |
| `user:prefs:{user_id}` | JSON string of user preferences | 1 hour | Preferences cache |
| `ws:active:{user_id}` | SET of connection_ids | No TTL | Active WebSocket connections |
| `inference:cache:{audio_hash}` | JSON inference result | 7 days | Duplicate chunk inference cache |

### 7.4 S3 Bucket Layout

```
sleepsense-audio-{env}/
└── {user_id}/{session_id}/chunk_{000..N}.opus

sleepsense-assets-{env}/
├── profiles/{user_id}/avatar.jpg
├── spectrograms/{session_id}/{chunk_id}.png
└── reports/{user_id}/{session_id}/report.pdf

sleepsense-ml-{env}/
├── models/snore_classifier_v*.pt
├── models/intensity_regressor_v*.pt
├── models/tflite/snore_classifier_v*_quantized.tflite
└── training-data/raw/ and /processed/
```

---

## 8. External Interface Requirements

### 8.1 REST API

| Convention | Standard |
|-----------|---------|
| Base URL | `https://api.sleepsense.app/v1` |
| Authentication | `Authorization: Bearer <JWT_access_token>` |
| Content-Type | `application/json` (except file uploads: `multipart/form-data`) |
| API Versioning | URL path: `/v1/`, `/v2/` |
| Error format | RFC 7807 Problem Details JSON |
| Pagination | Cursor-based (`?cursor=<token>&limit=20`) |
| Dates | ISO 8601 (`2025-01-15T22:30:00Z`) |
| IDs | UUID v4 |

**Complete Endpoint Reference:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | No | Create account |
| POST | `/auth/login` | No | Email/password login |
| POST | `/auth/refresh` | No | Rotate access token |
| POST | `/auth/logout` | Yes | Invalidate refresh token |
| POST | `/auth/social/google` | No | Google OAuth2 |
| POST | `/auth/social/apple` | No | Apple Sign-In (required for iOS App Store — FR-AUTH-006, COMP-012) |
| POST | `/auth/forgot-password` | No | Send reset email |
| POST | `/auth/reset-password` | No | Apply new password |
| GET | `/users/me` | Yes | Get own profile |
| PATCH | `/users/me` | Yes | Update profile |
| GET | `/users/me/health-profile` | Yes | Get health profile |
| PUT | `/users/me/health-profile` | Yes | Set health profile |
| POST | `/sessions` | Yes | Start session |
| POST | `/sessions/{id}/chunks` | Yes | Upload audio chunk |
| POST | `/sessions/{id}/end` | Yes | Finalize session |
| GET | `/sessions/{id}` | Yes | Session detail |
| GET | `/sessions/{id}/status` | Yes | Processing status |
| GET | `/sessions` | Yes | List sessions |
| DELETE | `/sessions/{id}/audio` | Yes | Delete session audio |
| GET | `/analytics/timeline/{id}` | Yes | Snoring timeline buckets |
| GET | `/analytics/trends` | Yes | 7/30/90-day trend |
| GET | `/analytics/weekly-summary` | Yes | Current week summary |
| GET | `/insights` | Yes | Get insights |
| PATCH | `/insights/{id}/read` | Yes | Mark insight read |
| POST | `/lifestyle-logs` | Yes | Log daily lifestyle |
| GET | `/lifestyle-logs` | Yes | List lifestyle logs |
| GET | `/sessions/export` | Yes | CSV export |
| DELETE | `/users/me` | Yes | Delete account (GDPR) |

### 8.2 Rate Limits

| Endpoint | Limit |
|----------|-------|
| `POST /auth/login` | 10 requests / 15 minutes per IP |
| `POST /auth/register` | 5 requests / hour per IP |
| `POST /sessions/*/chunks` | 120 requests / hour per user |
| `GET /analytics/*` | 60 requests / minute per user |
| All other authenticated endpoints | 100 requests / minute per user |

### 8.3 WebSocket API

| Item | Value |
|------|-------|
| URL | `wss://api.sleepsense.app/v1/ws?token=<access_token>` |
| Auth | JWT in query parameter |
| Heartbeat | Ping/pong every 30 seconds |
| Server events | `chunk.analyzed`, `session.complete` |

### 8.4 Mobile App Interface

| Platform | Framework | Min Version |
|----------|-----------|-------------|
| iOS | React Native + Expo | iOS 15+ |
| Android | React Native + Expo | Android 10 (API 29)+ |

**Required Permissions:**
- `RECORD_AUDIO` — mandatory; app is non-functional without it.
- `FOREGROUND_SERVICE` — Android; required to keep recording alive when backgrounded.
- `POST_NOTIFICATIONS` — Android 13+; for push notifications.
- `INTERNET` — for API communication.
- `RECEIVE_BOOT_COMPLETED` — to restore scheduled reminders after device restart.

### 8.5 Third-Party Integrations

| Integration | Purpose | Service |
|-------------|---------|---------|
| Google OAuth2 | Social login | Google Identity Platform |
| Apple Sign-In | Social login (iOS required) | Apple Developer |
| FCM | Android push notifications | Firebase Cloud Messaging |
| APNs | iOS push notifications | Apple Push Notification Service |
| SendGrid | Transactional email | Twilio SendGrid |
| S3 / MinIO | Audio and asset storage | AWS S3 or self-hosted MinIO |

---

## 9. ML / AI Requirements

### 9.1 Model Requirements

| Model | Architecture | Input | Output | Accuracy Target | Latency Target |
|-------|-------------|-------|--------|----------------|----------------|
| Snore Classifier | EfficientNet-B0 (transfer from AudioSet) | (1, 128, 128) Mel spectrogram | 4-class softmax: snoring/breathing/silence/ambient | F1 > 92% | < 50 ms/window (CPU) |
| Intensity Regressor | XGBoost GBT | 40 MFCCs + delta + delta-delta + RMS + ZCR + spectral centroid + rolloff + pitch + formant | Float 0–100 | MAE < 5 pts | < 10 ms/window |
| TFLite (mobile) | INT8 quantized EfficientNet-B0 | Same as Classifier | Same as Classifier | ≥ 90% of full model | < 100 ms/window (ARM Cortex-A55) |
| Sleep Stage Estimator | BiLSTM + Attention | 30s audio + optional accelerometer | Awake/Light/Deep/REM | TBD | Phase 2 |
| Apnea Risk Screener | Binary classifier | 7-night session features | Low/Medium/High risk | TBD | Phase 2 |

### 9.2 Feature Engineering Requirements

| Feature Group | Features | Used By |
|---------------|---------|---------|
| Spectral | 128-band Mel spectrogram (3s window), Log-Mel spectrogram | CNN Classifier |
| MFCC | 40 MFCCs + 40 delta MFCCs + 40 delta-delta MFCCs | XGBoost Regressor |
| Prosodic | RMS Energy, Zero-Crossing Rate, Spectral Centroid, Spectral Rolloff, Pitch F0, Formant F1 | XGBoost Regressor |

Audio preprocessing before feature extraction:
1. Resample to 16 kHz mono
2. Normalize amplitude (peak)
3. Remove DC offset
4. Trim silence (threshold: -40 dBFS)
5. Segment into 3-second windows (50% overlap)

### 9.3 Training Pipeline Requirements

| Requirement | Detail |
|-------------|--------|
| Orchestration | Apache Airflow DAG: `snore_model_training` |
| Frequency | Weekly automated + manual trigger |
| Data validation | Schema check, class distribution, SMOTE if class ratio > 5:1 |
| Augmentation | Time stretch (0.8–1.2×), pitch shift (±2 semitones), Gaussian noise, room simulation (RT60 0.1–0.8s), volume variation (±6 dB), time shift (±0.2s) |
| Classifier training | EfficientNet-B0; freeze backbone → train head (5 epochs); unfreeze → fine-tune (20 epochs); LR cosine decay from 1e-4 |
| Pipeline gate | F1 < 0.90 → pipeline fails; no model promoted |
| Experiment tracking | MLflow (all metrics, params, artifacts) |
| Model promotion | New model vs. production; if F1 improves > 1% → promote to candidate for A/B test |
| TFLite export | INT8 post-training quantization; accuracy within 2% of full-precision; upload to S3 |

### 9.4 Training Data Requirements

| Dataset | Volume | Classes | Source |
|---------|--------|---------|--------|
| ESC-50 | 2,000 samples | Environmental sounds (breathing/snoring subset) | Public / Kaggle |
| Snoring Dataset | 10,000 samples | Snoring vs. non-snoring | Kaggle |
| Custom collected | ~5,000 samples | All 4 classes from real users | In-app opt-in (Phase 2) |
| Synthetic augmented | ~50,000 samples | All 4 classes (generated in pipeline) | Generated |

Bias mitigation: stratify dataset by age group, gender, and available ethnicity proxies; report per-group precision and recall metrics alongside aggregate metrics.

### 9.5 ML Serving Requirements

| Requirement | Detail |
|-------------|--------|
| Model loading | Model Manager loads from S3 at startup; hot-reload when new model registered |
| GPU workers | 2 NVIDIA T4 GPU replicas for CNN classifier |
| CPU workers | 4 replicas for XGBoost intensity regressor |
| Inference cache | Redis key: `inference:cache:{hash(audio_features)}`; TTL 7 days; prevents re-inference of identical chunks |
| A/B testing | Model Manager supports traffic splitting (e.g., 90% v1.2 / 10% v1.3) |
| Auto-scaling | KEDA ScaledObject based on Kafka consumer lag; min 2, max 8 replicas |

### 9.6 Model Monitoring Requirements

| Metric | Alert Threshold |
|--------|----------------|
| Model accuracy (weekly spot-check on 1% of predictions vs. user feedback) | Drop > 5% week-over-week → PagerDuty alert |
| Feature distribution drift (KS test) | p-value < 0.05 → alert #ml-ops Slack channel |
| Inference latency P95 | > 5 seconds → PagerDuty alert |
| Kafka consumer lag | > 1,000 messages → #ml-ops alert |
| User correction rate | > 15% (users marking "not snoring") → review trigger |

Tool: Evidently AI for drift detection.

### 9.7 Ethical AI Requirements

| Concern | Requirement |
|---------|-------------|
| Medical claims | App labeled as "wellness tool, not a medical device" in all UI text, App Store descriptions, and API responses |
| Apnea risk threshold | Confidence ≥ 0.85 required before showing any risk alert (Phase 2) |
| Explainability | Grad-CAM heatmaps on mel spectrograms available in debug/pro mode to explain classification decisions |
| Training data consent | User audio used for model training only with explicit opt-in consent (separate toggle from account creation) |
| Data minimization | On-device TFLite option means audio never leaves the device if privacy mode is enabled |

---

## 10. Infrastructure & Deployment Requirements

### 10.1 Kubernetes Cluster

| Service | Min Replicas | Max Replicas | Scaling Trigger |
|---------|-------------|-------------|----------------|
| auth-service | 2 | 5 | CPU > 70% |
| audio-ingestion-service | 2 | 10 | CPU > 70% |
| ml-inference-service | 2 | 8 | Kafka lag > 100 messages (KEDA) |
| analytics-service | 2 | 6 | CPU > 70% |
| insight-engine | 2 | 4 | CPU > 70% |
| notification-service | 2 | 4 | CPU > 70% |

### 10.2 Managed Cloud Services

| Service | Technology | Configuration |
|---------|-----------|---------------|
| Relational DB | RDS PostgreSQL 16 | Multi-AZ, 1 primary + 2 read replicas |
| Cache | ElastiCache Redis 7 | Cluster mode, 3 shards |
| Message Broker | MSK (Managed Kafka) | 3 brokers, 3 AZs |
| Object Storage | AWS S3 | Cross-region replication; lifecycle rules for auto-expiry |
| Time-Series DB | InfluxDB Cloud | or self-hosted on K8s |
| CDN / WAF / DDoS | CloudFlare | Sits in front of load balancer |

### 10.3 Environment Strategy

| Environment | Infrastructure | Purpose |
|------------|---------------|---------|
| `local` | Docker Compose | Developer laptops; Postgres + Redis + Kafka + InfluxDB + MinIO |
| `dev` | K8s single-node | Integration testing between services |
| `staging` | K8s scaled-down production | Pre-production validation, E2E tests, load tests |
| `prod` | K8s full multi-AZ | Live users |

### 10.4 CI/CD Pipeline (GitHub Actions)

**Pull Request checks (parallel):**
- Lint: `ruff` (Python), `eslint` (TypeScript)
- Type check: `mypy` (Python), `tsc --noEmit` (TypeScript)
- Unit tests: `pytest` (Python), `jest` (TypeScript)
- Security scan: `trivy` (container images), `bandit` (Python)

**Merge to main:**
1. Build Docker images tagged with `git SHA`
2. Run integration tests (`docker-compose`)
3. Validate ML model if model files changed
4. Push images to AWS ECR

**Staging deploy:**
1. `helm upgrade sleepsense-staging`
2. E2E tests (Playwright)
3. Load test: k6 with 100 virtual users

**Production deploy:**
1. Blue-Green deployment (zero downtime)
2. Smoke tests
3. Monitor error rate for 10 minutes post-deploy
4. Auto-rollback if error rate > 1%

### 10.5 Observability

| Layer | Tool | What is Monitored |
|-------|------|------------------|
| Metrics | Prometheus + Grafana | Request rate, error rate, latency, CPU/memory, DAU, sessions/day, ML inference time, Kafka lag |
| Logging | ELK Stack (Elasticsearch + Logstash + Kibana) | Structured JSON logs from all services; correlation IDs for request tracing |
| Tracing | Jaeger / OpenTelemetry | Distributed trace: API Gateway → Service → DB → Kafka |
| Alerting | PagerDuty + Slack | P1: error rate > 5% → page on-call; P2: ML lag > 5 min → #ml-ops; P3: daily business metrics digest |

### 10.6 Disaster Recovery

| Metric | Target |
|--------|--------|
| RTO (P1 incident recovery time) | < 1 hour |
| RPO (maximum data loss) | < 5 minutes |
| PostgreSQL backup | Daily automated snapshots + continuous WAL streaming replication |
| S3 audio backup | Cross-region replication (async, ~15-second lag) |
| Failover | Multi-AZ RDS automatic failover < 60 seconds |

### 10.7 Cost Targets

| Scale | Monthly Infrastructure Cost |
|-------|-----------------------------|
| MVP (100 DAU) | ~$30–50 (Railway/Render/Fly.io + managed PostgreSQL) |
| Growth (10,000 DAU) | ~$1,225 (full AWS stack) |

---

## 11. Security Requirements

### 11.1 Authentication & Authorization

| ID | Requirement |
|----|-------------|
| SEC-001 | All API endpoints (except auth/register, auth/login, auth/social/*) require a valid JWT Bearer token. |
| SEC-002 | JWT access token TTL: 15 minutes. Refresh token TTL: 30 days with rotation on each use. |
| SEC-003 | RBAC implemented: `user`, `admin`, `researcher` roles. Role encoded in JWT claims. |
| SEC-004 | OAuth2 tokens (Google/Apple) validated server-side; never trusted from client. |
| SEC-005 | API Gateway validates JWT signature before routing to any microservice. |

### 11.2 Transport Security

| ID | Requirement |
|----|-------------|
| SEC-006 | All external traffic over TLS 1.3; TLS 1.2 allowed for legacy; TLS 1.0/1.1 disabled. |
| SEC-007 | HSTS (HTTP Strict Transport Security) header enforced. |
| SEC-008 | WebSocket connections over WSS (TLS). |

### 11.3 Data Security

| ID | Requirement |
|----|-------------|
| SEC-009 | Audio files encrypted at rest in S3 using AES-256 (SSE-S3 or SSE-KMS). |
| SEC-010 | PostgreSQL database encrypted at rest (AWS RDS encryption enabled). |
| SEC-011 | Passwords stored as bcrypt hashes (cost factor ≥ 12). |
| SEC-012 | PII (name, email, date of birth) anonymized in analytics pipelines used for research. |
| SEC-013 | Pre-signed S3 URLs for audio playback expire in 15 minutes. |
| SEC-014 | Redis refresh tokens stored as hashed values; raw tokens never persisted. |

### 11.4 API Security

| ID | Requirement |
|----|-------------|
| SEC-015 | All request bodies validated with Pydantic schemas before processing. |
| SEC-016 | Rate limiting enforced at API Gateway level (see Section 8.2). |
| SEC-017 | Login endpoint returns generic error messages to prevent user enumeration. |
| SEC-018 | CORS: only allowed origins (`https://sleepsense.app`, `https://api.sleepsense.app`). |
| SEC-019 | File upload validation: MIME type checked against allowlist; max size enforced server-side. |
| SEC-020 | SQL injection prevention: all DB queries via SQLAlchemy ORM with parameterized queries. |

### 11.5 Audit & Monitoring

| ID | Requirement |
|----|-------------|
| SEC-021 | All authentication events (login, logout, failed login, token refresh) logged with IP and timestamp. |
| SEC-022 | Admin actions logged to immutable audit log. |
| SEC-023 | Container images scanned for vulnerabilities (Trivy) in CI/CD pipeline before every deployment. |
| SEC-024 | Static code analysis (Bandit for Python) runs on every PR. |

---

## 12. Compliance & Legal Requirements

### 12.1 GDPR Compliance

| ID | Requirement |
|----|-------------|
| COMP-001 | Users must explicitly consent to data collection before account creation. |
| COMP-002 | Privacy Policy must be accessible from the app without logging in. |
| COMP-003 | User can delete their account and all data (Right to Erasure) — completed within 30 days. |
| COMP-004 | User can export all their data in machine-readable format (Right to Portability) — CSV export (FR-HIST-006). |
| COMP-005 | Audio used for ML model training only with explicit secondary consent (separate opt-in toggle). |
| COMP-006 | Data Processing Agreement (DPA) required with all third-party processors (AWS, SendGrid, Google). |

### 12.2 Health Claim Boundaries

| ID | Requirement |
|----|-------------|
| COMP-007 | App must NOT present itself as a medical device, diagnostic tool, or clinical instrument. |
| COMP-008 | All references to apnea risk (Phase 2) must include: "This is not a medical diagnosis. Consult a licensed physician." |
| COMP-009 | App Store and Play Store descriptions must not use the words: "diagnose", "treat", "cure", "medical advice." |
| COMP-010 | In Phase 2, apnea risk screener requires review and sign-off from a qualified sleep medicine consultant before release. |
| COMP-011 | Confidence threshold of ≥ 0.85 required before any risk alert is surfaced to the user. |

### 12.3 App Store Compliance

| ID | Requirement |
|----|-------------|
| COMP-012 | iOS: Apple Sign-In must be offered as a login option (App Store Review Guideline 4.8). |
| COMP-013 | iOS: Background audio recording must use the `audio` background mode declared in `Info.plist`. |
| COMP-014 | iOS: App must request `NSMicrophoneUsageDescription` with clear, user-facing explanation. |
| COMP-015 | Android: `FOREGROUND_SERVICE_MICROPHONE` permission declared in `AndroidManifest.xml` (Android 14+). |

---

## 13. Out of Scope (Phase 1)

The following are explicitly **deferred to Phase 2 or later**:

| Feature | Phase | Reason |
|---------|-------|--------|
| Sleep stage detection (REM/Light/Deep/Awake) | Phase 2 | Requires wearable data for reliable results; audio-only accuracy is misleading |
| Apnea risk screener | Phase 2 | Regulatory risk; requires medical consultant sign-off before release |
| Wearable integration (WatchOS, Fitbit, Google Fit) | Phase 2 | SDK complexity; not required for MVP |
| Web dashboard (React) | Phase 2 | Mobile-first strategy; web adds backend complexity |
| Subscription payments (Stripe/Razorpay) | Phase 3 | Focus on user acquisition before monetization |
| Social features (sharing, leaderboards) | Phase 3+ | Privacy-sensitive health data; trust must be built first |
| Doctor-share PDF reports | Phase 3 | Requires clinical validation of report format |
| LLM-powered insights (beyond rule-based) | Phase 3 | Cost and hallucination risk; rule-based sufficient for MVP |
| International expansion | Phase 4 | India-first; localization and regulatory complexity deferred |
| B2B hospital / clinic partnerships | Phase 4 | Requires HIPAA-compliant features and enterprise sales |

---

## 14. Glossary

| Term | Definition |
|------|-----------|
| Access Token | Short-lived JWT (15 min) used to authenticate API requests |
| Audio Chunk | 30-second segment of recorded sleep audio |
| Confidence Score | The max softmax probability output by the CNN, indicating model certainty |
| DAU | Daily Active Users |
| Dominant Class | The sound class with highest CNN probability for a given 3-second window |
| EfficientNet-B0 | A CNN architecture optimized for accuracy-efficiency trade-off; used for snore classification |
| Insight | A personalized sleep tip or warning generated after each session |
| MAU | Monthly Active Users |
| Mel-Frequency Cepstral Coefficient (MFCC) | A feature representing the short-term power spectrum of audio on the mel scale, used by the intensity regressor |
| Mel Spectrogram | A visual representation of audio frequency content over time, mapped to the mel scale; the CNN input |
| On-device Mode | TFLite inference running on the phone; audio never uploaded to the cloud |
| Refresh Token | Long-lived token (30 days) used to obtain new access tokens without re-login |
| Session | A complete overnight sleep recording from start to end |
| Sleep Quality Score | A 0–100 composite score representing the overall quality of one night's sleep |
| Sleep Stage | A phase of sleep (Awake/Light/Deep/REM); tracked in Phase 2 |
| Snore Intensity | A 0–100 score representing how loud/severe a snoring event is |
| TFLite | TensorFlow Lite — a lightweight runtime for running ML models on mobile devices |
| Upload Token | Short-lived token issued with session creation to authorize chunk uploads |

---

*End of SRS v2.0 · SleepSense · May 2026*
