# Database Design
## SleepSense — Polyglot Persistence Strategy

---

## 1. Database Selection Rationale

| Database    | Used For                                           | Why                                          |
|-------------|---------------------------------------------------|----------------------------------------------|
| PostgreSQL  | Users, sessions, analytics summaries, app config   | ACID, complex queries, relational integrity  |
| Redis       | JWT refresh tokens, rate limiting, session cache   | Sub-millisecond reads, TTL support           |
| InfluxDB    | Timestamped snore events, raw metrics stream       | Purpose-built for time-series data           |
| S3 / MinIO  | Raw audio files, spectrograms, ML model artifacts  | Cheap, durable object storage                |

---

## 2. PostgreSQL Schema

### Table: users
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255),                         -- NULL for social-only accounts
    display_name    VARCHAR(100),
    date_of_birth   DATE,
    gender          VARCHAR(20),
    weight_kg       DECIMAL(5,1),
    height_cm       DECIMAL(5,1),
    profile_image   VARCHAR(500),                         -- S3 URL
    timezone        VARCHAR(50) DEFAULT 'UTC',
    is_active       BOOLEAN DEFAULT TRUE,
    is_verified     BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Table: social_accounts
```sql
CREATE TABLE social_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    provider        VARCHAR(20) NOT NULL,                 -- 'google', 'apple'
    provider_uid    VARCHAR(255) NOT NULL,
    access_token    TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider, provider_uid)
);
```

### Table: user_health_profile
```sql
CREATE TABLE user_health_profile (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    sleep_position          VARCHAR(20),                  -- 'back', 'side', 'stomach'
    known_conditions        TEXT[],                       -- ['sleep_apnea', 'deviated_septum']
    medications             TEXT[],
    alcohol_frequency       VARCHAR(20),
    smoking_status          VARCHAR(20),
    cpap_user               BOOLEAN DEFAULT FALSE,
    snoring_severity_self   INTEGER CHECK (snoring_severity_self BETWEEN 1 AND 5),
    updated_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Table: sleep_sessions
```sql
CREATE TABLE sleep_sessions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID REFERENCES users(id) ON DELETE CASCADE,
    started_at              TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at                TIMESTAMP WITH TIME ZONE,
    duration_minutes        INTEGER,
    status                  VARCHAR(20) DEFAULT 'recording',  -- 'recording','processing','complete','failed'

    -- Computed after analysis
    sleep_quality_score     DECIMAL(5,2),                 -- 0–100
    sleep_quality_grade     VARCHAR(10),                  -- 'Excellent','Good','Fair','Poor','Critical'
    snoring_duration_min    INTEGER,
    snoring_percentage      DECIMAL(5,2),
    snore_events_per_hour   DECIMAL(5,2),
    avg_snore_intensity     DECIMAL(5,2),
    max_snore_intensity     DECIMAL(5,2),
    peak_snoring_hour       INTEGER,                      -- hour of night (0–23)
    total_chunks            INTEGER DEFAULT 0,
    processed_chunks        INTEGER DEFAULT 0,

    -- Environmental context
    room_temperature        DECIMAL(4,1),
    humidity_percent        INTEGER,
    notes                   TEXT,                         -- user notes

    created_at              TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sessions_user_started ON sleep_sessions(user_id, started_at DESC);
CREATE INDEX idx_sessions_status ON sleep_sessions(status) WHERE status != 'complete';
```

### Table: audio_chunks
```sql
CREATE TABLE audio_chunks (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID REFERENCES sleep_sessions(id) ON DELETE CASCADE,
    chunk_index         INTEGER NOT NULL,
    s3_key              VARCHAR(500) NOT NULL,
    duration_seconds    INTEGER NOT NULL,
    file_size_bytes     INTEGER,
    mime_type           VARCHAR(50),
    uploaded_at         TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at        TIMESTAMP WITH TIME ZONE,
    status              VARCHAR(20) DEFAULT 'pending',    -- 'pending','processing','done','failed'
    analysis_result     JSONB,                            -- raw ML output stored here
    UNIQUE(session_id, chunk_index)
);
```

### Table: session_insights
```sql
CREATE TABLE session_insights (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID REFERENCES sleep_sessions(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    insight_type    VARCHAR(50) NOT NULL,                 -- 'tip','warning','achievement','trend'
    priority        INTEGER DEFAULT 0,                    -- higher = shown first
    title           VARCHAR(200) NOT NULL,
    body            TEXT NOT NULL,
    action_url      VARCHAR(500),                         -- deep link for CTA
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Table: weekly_summaries
```sql
CREATE TABLE weekly_summaries (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID REFERENCES users(id) ON DELETE CASCADE,
    week_start              DATE NOT NULL,
    week_end                DATE NOT NULL,
    nights_recorded         INTEGER DEFAULT 0,
    avg_sleep_duration_min  INTEGER,
    avg_quality_score       DECIMAL(5,2),
    avg_snore_percentage    DECIMAL(5,2),
    best_night_session_id   UUID REFERENCES sleep_sessions(id),
    worst_night_session_id  UUID REFERENCES sleep_sessions(id),
    trend_direction         VARCHAR(10),                  -- 'improving','declining','stable'
    generated_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, week_start)
);
```

### Table: lifestyle_logs
```sql
CREATE TABLE lifestyle_logs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES users(id) ON DELETE CASCADE,
    logged_date         DATE NOT NULL,
    alcohol_units       DECIMAL(3,1),
    exercise_minutes    INTEGER,
    stress_level        INTEGER CHECK (stress_level BETWEEN 1 AND 5),
    caffeine_cups       INTEGER,
    sleep_aid_used      BOOLEAN DEFAULT FALSE,
    notes               TEXT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, logged_date)
);
```

### Table: user_goals
```sql
CREATE TABLE user_goals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    goal_type       VARCHAR(50) NOT NULL,                 -- 'quality_score','recording_streak','reduce_snoring'
    target_value    DECIMAL(10,2),
    current_value   DECIMAL(10,2) DEFAULT 0,
    is_achieved     BOOLEAN DEFAULT FALSE,
    target_date     DATE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Table: notifications
```sql
CREATE TABLE notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    type            VARCHAR(50) NOT NULL,
    title           VARCHAR(200),
    body            TEXT,
    payload         JSONB,
    channel         VARCHAR(20) DEFAULT 'push',           -- 'push','email','in_app'
    sent_at         TIMESTAMP WITH TIME ZONE,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 3. InfluxDB Schema (Time-Series)

### Measurement: snore_events
```
Tags (indexed):
  session_id   = "uuid-string"
  user_id      = "uuid-string"
  event_class  = "snoring" | "breathing" | "silence" | "ambient"

Fields:
  intensity        float   (0.0 – 100.0)
  confidence       float   (0.0 – 1.0)
  chunk_index      integer
  window_index     integer

Timestamp: epoch nanoseconds (absolute time within sleep session)
```

### Measurement: session_metrics (5-min aggregated buckets)
```
Tags:
  session_id, user_id

Fields:
  avg_intensity      float
  snore_event_count  integer
  dominant_class     string
  decibel_estimate   float

Timestamp: start of 5-minute bucket
```

### Sample Query — Snoring timeline for one session
```flux
from(bucket: "sleepsense")
  |> range(start: 2025-01-01T22:00:00Z, stop: 2025-01-02T06:00:00Z)
  |> filter(fn: (r) => r._measurement == "session_metrics")
  |> filter(fn: (r) => r.session_id == "abc-123")
  |> aggregateWindow(every: 5m, fn: mean, createEmpty: true)
  |> yield(name: "timeline")
```

---

## 4. Redis Data Structures

```
# Refresh tokens (per user session)
Key:   refresh:{user_id}:{device_id}
Value: {token_hash, issued_at, expires_at, device_info}
TTL:   30 days

# Rate limiting (login attempts)
Key:   ratelimit:login:{ip_address}
Value: count integer (INCR)
TTL:   15 minutes

# Session processing status cache
Key:   session:status:{session_id}
Value: {status, processed_chunks, total_chunks, last_updated}
TTL:   24 hours

# User preferences cache (avoid DB hit on every request)
Key:   user:prefs:{user_id}
Value: JSON string of user preferences
TTL:   1 hour

# Active WebSocket connections
Key:   ws:active:{user_id}
Value: SET of connection_ids
TTL:   No TTL (removed on disconnect)
```

---

## 5. S3 Storage Organization

```
Bucket: sleepsense-audio-{env}
├── {user_id}/
│   └── {session_id}/
│       ├── chunk_000.opus
│       ├── chunk_001.opus
│       └── ...

Bucket: sleepsense-assets-{env}
├── profiles/{user_id}/avatar.jpg
├── spectrograms/{session_id}/{chunk_id}.png     ← for debugging/visualization
└── reports/{user_id}/{session_id}/report.pdf    ← generated PDF reports

Bucket: sleepsense-ml-{env}
├── models/
│   ├── snore_classifier_v1.2.pt
│   ├── snore_classifier_v1.3.pt         ← staged for A/B test
│   └── intensity_regressor_v1.0.pt
└── training-data/
    ├── raw/                              ← uploaded by data team
    └── processed/                       ← features ready for training
```

---

## 6. Data Retention & GDPR Compliance

| Data Type           | Retention          | Deletion Policy                            |
|---------------------|--------------------|--------------------------------------------|
| Raw audio files     | 12 months          | Auto-deleted, user can delete anytime      |
| Snore event metrics | 24 months          | Anonymized after user deletion             |
| Session summaries   | Indefinite         | Deleted on account deletion                |
| Insights/Tips       | 6 months           | Purged in background job                   |
| Notification logs   | 90 days            | Rolling purge                              |

On account deletion: cascade delete all PII; anonymize InfluxDB metrics (remove user_id tag, retain aggregated data for research with consent).
