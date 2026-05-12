# Low-Level Design (LLD)
## SleepSense — Detailed Component Specifications

---

## 1. Microservice Internal Architecture

Every microservice follows a clean **Layered Architecture**:

```
┌───────────────────────────────────────┐
│           API / Controller Layer       │  ← FastAPI routes, request validation
├───────────────────────────────────────┤
│             Service Layer             │  ← Business logic, orchestration
├───────────────────────────────────────┤
│           Repository Layer            │  ← DB queries, data access objects
├───────────────────────────────────────┤
│             Domain Layer              │  ← Pydantic models, enums, constants
├───────────────────────────────────────┤
│         Infrastructure Layer          │  ← DB connections, S3 client, Kafka
└───────────────────────────────────────┘
```

---

## 2. Auth Service — LLD

### Responsibilities
- User registration, login, logout
- JWT access token (15 min TTL) + refresh token (30 days TTL)
- OAuth2 social login (Google, Apple)
- Password hashing (bcrypt)
- Rate limiting on login endpoint

### Endpoints
```
POST /auth/register          → Create account
POST /auth/login             → Returns access_token + refresh_token
POST /auth/refresh           → Rotate tokens
POST /auth/logout            → Invalidate refresh token
POST /auth/social/google     → Google OAuth2 callback
POST /auth/forgot-password   → Send reset email
POST /auth/reset-password    → Apply new password
```

### Internal Flow — Login
```
Client POST /auth/login {email, password}
    │
    ▼
Validate request schema (Pydantic)
    │
    ▼
Lookup user by email in PostgreSQL
    │
    ▼
bcrypt.checkpw(password, stored_hash)
    │
    ├─ FAIL → 401 Unauthorized (generic message, no user enum)
    │
    └─ PASS →
        ├── Generate JWT (sub=user_id, exp=15min, roles=[user])
        ├── Generate refresh token (UUID, store in Redis with TTL 30d)
        └── Return {access_token, refresh_token, expires_in}
```

---

## 3. Audio Ingestion Service — LLD

### Responsibilities
- Accept audio chunks from clients (multipart upload)
- Validate format (WAV/M4A/OGG, max 10MB/chunk)
- Store raw audio to S3
- Emit Kafka event for ML pipeline
- Handle session lifecycle (start/end)

### Endpoints
```
POST /sessions/start              → Create sleep session, return session_id
POST /sessions/{id}/chunks        → Upload audio chunk (multipart)
POST /sessions/{id}/end           → Finalize session
GET  /sessions/{id}/status        → Get processing status
DELETE /sessions/{id}             → Delete session + audio (GDPR)
```

### Chunk Upload Flow
```
Client: POST /sessions/{id}/chunks
  Header: Content-Type: multipart/form-data
  Body: {
    chunk_index: 3,
    duration_seconds: 30,
    audio_file: <binary>
  }
        │
        ▼
Validate: session exists, belongs to user, chunk_index sequential
        │
        ▼
Compress audio (if raw PCM → opus encode for storage efficiency)
        │
        ▼
Upload to S3: s3://sleepsense-audio/{user_id}/{session_id}/{chunk_index}.opus
        │
        ▼
Insert into PostgreSQL:
  audio_chunks table: (chunk_id, session_id, s3_key, duration, uploaded_at)
        │
        ▼
Publish Kafka message to topic "audio.chunk.uploaded":
  {
    "chunk_id": "uuid",
    "session_id": "uuid",
    "user_id": "uuid",
    "s3_key": "path/to/chunk.opus",
    "chunk_index": 3,
    "duration_seconds": 30,
    "timestamp": "ISO8601"
  }
        │
        ▼
Return 202 Accepted {chunk_id, status: "processing"}
```

---

## 4. ML Inference Service — LLD

### Responsibilities
- Consume Kafka events for new audio chunks
- Load and preprocess audio
- Run snore classification model
- Run snore intensity regression model
- Store results to InfluxDB + PostgreSQL
- Emit "analysis.complete" event

### Processing Pipeline
```
Kafka Consumer receives: {chunk_id, s3_key, session_id}
        │
        ▼
Download audio from S3 (streaming, not full load)
        │
        ▼
Audio Preprocessing:
  ├── Decode opus → PCM float32 (16kHz mono)
  ├── Noise floor detection (silence trimming)
  ├── Segment into 3-second windows (50% overlap)
  └── Compute Mel spectrogram per window:
        - n_mels=128, hop_length=512, n_fft=2048
        - Normalize to [-1, 1]
        │
        ▼
CNN Classifier (per window):
  Input: (1, 128, 128) mel spectrogram
  Output: {snoring: 0.87, breathing: 0.10, silence: 0.02, ambient: 0.01}
        │
        ▼
Intensity Regressor (for snore windows only):
  Input: same spectrogram + MFCC deltas
  Output: snore_intensity float [0.0 – 100.0]
        │
        ▼
Aggregate windows → chunk-level results:
  {
    snore_windows: 14,
    total_windows: 20,
    snore_ratio: 0.70,
    avg_intensity: 62.4,
    max_intensity: 88.1,
    events: [{start_sec: 0.0, end_sec: 3.0, class: "snoring", intensity: 71.2}, ...]
  }
        │
        ├── Write to InfluxDB (measurement: snore_events, tags: session_id, user_id)
        ├── Update PostgreSQL audio_chunks.analysis_result
        │
        ▼
Publish Kafka: "analysis.complete" {session_id, chunk_id, summary}
```

### CNN Model Architecture
```
Input: Mel Spectrogram (1 × 128 × 128)
    │
    ▼
Conv2D(32, 3×3, ReLU) → BatchNorm → MaxPool(2×2)
    │
Conv2D(64, 3×3, ReLU) → BatchNorm → MaxPool(2×2)
    │
Conv2D(128, 3×3, ReLU) → BatchNorm → MaxPool(2×2)
    │
Conv2D(256, 3×3, ReLU) → BatchNorm → GlobalAvgPool
    │
FC(512, ReLU) → Dropout(0.4)
    │
FC(4, Softmax) → {snoring, breathing, silence, ambient}
```

---

## 5. Analytics Service — LLD

### Responsibilities
- Aggregate per-chunk results into session-level stats
- Compute sleep quality score algorithm
- Generate trend data (week/month views)
- Trigger insight generation
- Serve dashboard API

### Sleep Quality Score Algorithm
```
Score = 100 − (
  (snore_ratio × 40)       +   // snoring impact (0–40 pts penalty)
  (avg_intensity/100 × 25) +   // intensity penalty (0–25 pts)
  (interruption_count × 2) +   // frequent events penalty
  (session_gap_penalty)        // if < 6h sleep, up to 15pt penalty
)
Clamp to [0, 100]

Grade:
  90–100 → Excellent
  75–89  → Good
  60–74  → Fair
  40–59  → Poor
  0–39   → Critical
```

### Session Summary Computation
```
Event: "session.ended" received
    │
    ▼
Query InfluxDB: all snore_events WHERE session_id = X
    │
    ▼
Compute:
  total_duration_minutes
  snoring_duration_minutes
  snoring_percentage
  snore_events_per_hour
  peak_snoring_hour
  loudest_event {timestamp, intensity}
  quiet_periods [{start, end, duration}]
  sleep_quality_score (0–100)
  sleep_quality_grade
    │
    ▼
Build noise_timeline:
  Bin events into 5-minute buckets → intensity values for chart
    │
    ▼
Store to PostgreSQL: sleep_sessions table
    │
    ▼
Kafka: "insights.generate" {session_id, user_id, session_summary}
```

---

## 6. Insight Engine — LLD

### Responsibilities
- Pattern detection across historical sessions
- Rule-based + LLM-based recommendation generation
- Personalized tips based on user profile (age, weight, sleep position)

### Rule Engine
```python
Rules applied (in priority order):

1. POSITIONAL_SNORING:
   IF peak_snoring correlates with back-sleeping position (via IMU data)
   THEN suggest: "Try sleeping on your side"

2. ALCOHOL_CORRELATION:
   IF user logs alcohol consumption AND snore_score > 70 same night
   THEN suggest: "Alcohol significantly worsens snoring"

3. CHRONIC_SNORING:
   IF snore_score > 60 for 5+ consecutive nights
   THEN suggest: "Consider consulting a sleep specialist (possible sleep apnea)"

4. IMPROVEMENT_TREND:
   IF avg_score improved by > 15 points over 7 days
   THEN generate positive reinforcement message

5. SLEEP_DEBT:
   IF avg_sleep_duration < 6h over 5 days
   THEN suggest sleep hygiene improvements
```

---

## 7. Notification Service — LLD

### Channels
- Push Notification (FCM for Android, APNs for iOS)
- Email (SendGrid)
- In-app notification (WebSocket / polling)

### Notification Types
```
SLEEP_REPORT_READY    → sent when session analysis completes
WEEKLY_SUMMARY        → sent every Monday morning
GOAL_ACHIEVED         → sent when streak/improvement goal met
HEALTH_ALERT          → sent if chronic patterns detected
REMINDER              → configurable bedtime reminder
```

---

## 8. Project Directory Structure

```
sleepsense/
│
├── services/
│   ├── auth-service/
│   │   ├── app/
│   │   │   ├── api/routes/          # FastAPI route handlers
│   │   │   ├── core/security.py     # JWT logic
│   │   │   ├── models/user.py       # SQLAlchemy models
│   │   │   ├── schemas/             # Pydantic schemas
│   │   │   └── main.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── audio-ingestion-service/
│   ├── ml-inference-service/
│   │   ├── app/
│   │   │   ├── models/              # PyTorch model definitions
│   │   │   ├── pipeline/
│   │   │   │   ├── preprocessor.py  # Audio → Mel spectrogram
│   │   │   │   ├── classifier.py    # CNN inference
│   │   │   │   └── aggregator.py    # Window → chunk results
│   │   │   └── consumer.py          # Kafka consumer loop
│   │   └── weights/                 # Model checkpoint files
│   │
│   ├── analytics-service/
│   ├── notification-service/
│   └── insight-engine/
│
├── mobile/                          # React Native app
│   ├── src/
│   │   ├── screens/                 # RecordScreen, DashboardScreen, etc.
│   │   ├── components/              # Reusable UI components
│   │   ├── hooks/useAudioRecorder.ts
│   │   ├── api/                     # API client functions
│   │   └── store/                   # Zustand / Redux state
│   └── app.json
│
├── web/                             # React web dashboard
│   ├── src/
│   │   ├── pages/
│   │   ├── components/charts/
│   │   └── services/api.ts
│   └── package.json
│
├── ml-research/                     # Jupyter notebooks, experiments
│   ├── notebooks/
│   │   ├── 01_data_exploration.ipynb
│   │   ├── 02_feature_engineering.ipynb
│   │   ├── 03_model_training.ipynb
│   │   └── 04_model_evaluation.ipynb
│   └── datasets/                    # Dataset configs (not raw data)
│
├── infra/
│   ├── docker-compose.yml           # Local dev environment
│   ├── k8s/                         # Kubernetes manifests
│   └── terraform/                   # Cloud infrastructure as code
│
└── docs/                            # This directory
```
