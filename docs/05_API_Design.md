# API Design Specification
## SleepSense — RESTful API v1

---

## 1. API Conventions

| Convention         | Standard                                                   |
|--------------------|------------------------------------------------------------|
| Base URL           | `https://api.sleepsense.app/v1`                            |
| Authentication     | `Authorization: Bearer <JWT_access_token>`                 |
| Content-Type       | `application/json` (except file uploads: `multipart/form-data`) |
| Versioning         | URL-based (`/v1/`, `/v2/`)                                 |
| Errors             | RFC 7807 Problem Details format                            |
| Pagination         | Cursor-based (`?cursor=<token>&limit=20`)                  |
| Date format        | ISO 8601 (`2025-01-15T22:30:00Z`)                          |
| ID format          | UUID v4                                                    |

---

## 2. Standard Error Response

```json
{
  "type": "https://sleepsense.app/errors/validation_error",
  "title": "Validation Error",
  "status": 422,
  "detail": "The 'email' field must be a valid email address.",
  "instance": "/v1/auth/register",
  "errors": [
    {"field": "email", "message": "Invalid email format"}
  ]
}
```

---

## 3. Auth Endpoints

### POST /auth/register
```json
// Request
{
  "email": "user@example.com",
  "password": "SecurePass123!",
  "display_name": "John Doe"
}

// Response 201
{
  "user_id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "access_token": "eyJ...",
  "refresh_token": "uuid-refresh-token",
  "expires_in": 900
}
```

### POST /auth/login
```json
// Request
{ "email": "user@example.com", "password": "SecurePass123!" }

// Response 200
{
  "access_token": "eyJ...",
  "refresh_token": "uuid-refresh-token",
  "expires_in": 900,
  "user": { "id": "uuid", "display_name": "John Doe", "email": "..." }
}
```

### POST /auth/refresh
```json
// Request
{ "refresh_token": "uuid-refresh-token" }

// Response 200
{ "access_token": "eyJ...", "expires_in": 900 }
```

---

## 4. User & Profile Endpoints

### GET /users/me
```json
// Response 200
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "date_of_birth": "1995-04-15",
  "gender": "male",
  "weight_kg": 78.5,
  "height_cm": 175,
  "timezone": "Asia/Kolkata",
  "profile_image": "https://cdn.sleepsense.app/profiles/uuid/avatar.jpg",
  "created_at": "2025-01-01T10:00:00Z"
}
```

### PATCH /users/me
```json
// Request (partial update, only include fields to change)
{
  "display_name": "John",
  "weight_kg": 77.0,
  "timezone": "Asia/Kolkata"
}
```

### GET /users/me/health-profile
### PUT /users/me/health-profile
```json
// Request
{
  "sleep_position": "side",
  "known_conditions": ["allergies"],
  "alcohol_frequency": "occasionally",
  "smoking_status": "never",
  "cpap_user": false,
  "snoring_severity_self": 3
}
```

---

## 5. Sleep Session Endpoints

### POST /sessions  — Start a new recording session
```json
// Request
{
  "started_at": "2025-01-15T22:30:00Z",
  "timezone": "Asia/Kolkata"
}

// Response 201
{
  "session_id": "uuid",
  "status": "recording",
  "started_at": "2025-01-15T22:30:00Z",
  "upload_token": "short-lived-token-for-chunks"
}
```

### POST /sessions/{session_id}/chunks  — Upload audio chunk
```
Content-Type: multipart/form-data

Fields:
  chunk_index: integer (0-based, sequential)
  duration_seconds: integer
  audio: <binary file> (.opus, .wav, .m4a, max 10MB)

Response 202:
{
  "chunk_id": "uuid",
  "chunk_index": 0,
  "status": "queued",
  "message": "Chunk received, analysis queued"
}
```

### POST /sessions/{session_id}/end  — Finalize session
```json
// Request
{
  "ended_at": "2025-01-16T06:45:00Z",
  "notes": "Felt congested tonight",
  "room_temperature": 22.5
}

// Response 200
{
  "session_id": "uuid",
  "status": "processing",
  "estimated_ready_in_seconds": 120
}
```

### GET /sessions/{session_id}  — Get session details
```json
// Response 200 (when complete)
{
  "id": "uuid",
  "status": "complete",
  "started_at": "2025-01-15T22:30:00Z",
  "ended_at": "2025-01-16T06:45:00Z",
  "duration_minutes": 495,
  "sleep_quality_score": 72.4,
  "sleep_quality_grade": "Fair",
  "snoring_duration_min": 87,
  "snoring_percentage": 17.6,
  "snore_events_per_hour": 12.3,
  "avg_snore_intensity": 58.2,
  "max_snore_intensity": 89.4,
  "peak_snoring_hour": 2,
  "total_chunks": 60,
  "processed_chunks": 60
}
```

### GET /sessions  — List all sessions (paginated)
```json
// Query params: ?cursor=<token>&limit=20&from=2025-01-01&to=2025-01-31

// Response 200
{
  "sessions": [
    {
      "id": "uuid",
      "started_at": "...",
      "duration_minutes": 495,
      "sleep_quality_score": 72.4,
      "sleep_quality_grade": "Fair",
      "snoring_percentage": 17.6
    }
  ],
  "next_cursor": "eyJ...",
  "has_more": true,
  "total_count": 45
}
```

---

## 6. Analytics Endpoints

### GET /analytics/timeline/{session_id}  — Noise timeline for charts
```json
// Response 200
{
  "session_id": "uuid",
  "buckets": [
    {
      "timestamp": "2025-01-15T22:30:00Z",
      "avg_intensity": 0,
      "dominant_class": "silence",
      "snore_event_count": 0
    },
    {
      "timestamp": "2025-01-15T22:35:00Z",
      "avg_intensity": 62.1,
      "dominant_class": "snoring",
      "snore_event_count": 4
    }
    // ...one bucket per 5 minutes
  ],
  "bucket_size_minutes": 5
}
```

### GET /analytics/trends  — Weekly/monthly trends
```json
// Query: ?period=7d|30d|90d

// Response 200
{
  "period": "30d",
  "data_points": [
    {
      "date": "2025-01-01",
      "quality_score": 68.0,
      "snoring_percentage": 21.3,
      "duration_minutes": 420
    }
    // ...one per night
  ],
  "summary": {
    "avg_quality_score": 71.2,
    "avg_snoring_percentage": 18.4,
    "trend_direction": "improving",
    "trend_change_percent": 8.3,
    "nights_recorded": 22,
    "nights_missed": 8
  }
}
```

### GET /analytics/weekly-summary  — Current week snapshot
```json
// Response 200
{
  "week_start": "2025-01-13",
  "week_end": "2025-01-19",
  "nights_recorded": 5,
  "avg_quality_score": 73.1,
  "avg_snoring_percentage": 16.8,
  "avg_sleep_duration_minutes": 467,
  "best_night": { "date": "2025-01-17", "score": 88.2 },
  "worst_night": { "date": "2025-01-14", "score": 52.1 },
  "vs_previous_week": { "quality_change": +5.2, "snoring_change": -3.1 }
}
```

---

## 7. Insights Endpoints

### GET /insights  — Get personalized insights
```json
// Query: ?session_id=<uuid>  OR  latest insights if no session_id

// Response 200
{
  "insights": [
    {
      "id": "uuid",
      "type": "warning",
      "priority": 10,
      "title": "Consistent late-night snoring detected",
      "body": "Your snoring peaks between 2–4 AM. This may indicate positional snoring. Try sleeping on your side.",
      "action_label": "Learn more",
      "action_url": "sleepsense://tips/positional-snoring",
      "is_read": false,
      "created_at": "2025-01-16T07:00:00Z"
    }
  ]
}
```

### PATCH /insights/{insight_id}/read
```json
// Response 200
{ "id": "uuid", "is_read": true }
```

---

## 8. Lifestyle Log Endpoints

### POST /lifestyle-logs
```json
// Request
{
  "logged_date": "2025-01-15",
  "alcohol_units": 2.0,
  "exercise_minutes": 30,
  "stress_level": 3,
  "caffeine_cups": 2,
  "sleep_aid_used": false
}
```

### GET /lifestyle-logs  — List logs
```json
// Query: ?from=2025-01-01&to=2025-01-31
```

---

## 9. WebSocket API (Real-time)

### Connection
```
WSS: wss://api.sleepsense.app/v1/ws?token=<access_token>
```

### Server → Client Events
```json
// Analysis progress during active session
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

// Session analysis complete
{
  "event": "session.complete",
  "data": {
    "session_id": "uuid",
    "sleep_quality_score": 72.4,
    "summary_available": true
  }
}
```

---

## 10. Rate Limits

| Endpoint                    | Limit                 |
|-----------------------------|-----------------------|
| POST /auth/login            | 10 requests / 15 min  |
| POST /auth/register         | 5 requests / hour     |
| POST /sessions/*/chunks     | 120 requests / hour   |
| GET /analytics/*            | 60 requests / minute  |
| All other endpoints         | 100 requests / minute |
