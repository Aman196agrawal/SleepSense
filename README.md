# SleepSense — Sample Build

A full-stack sample of the SleepSense sleep/snoring analytics platform —
React Native mobile app, two FastAPI microservices, and a local infra stack
matching the production architecture (PostgreSQL, Redis, Kafka, InfluxDB,
MinIO).

## What's Running

| Layer | Technology | Port |
|-------|-----------|------|
| Auth Service        | Python FastAPI                       | 8001 |
| Analytics Service   | Python FastAPI                       | 8002 |
| PostgreSQL          | Users / sessions / lifestyle / insights | 5432 |
| Redis               | Refresh tokens, rate-limit counters | 6379 |
| Kafka (KRaft)       | `audio.chunk.uploaded`, `session.ended` topics | 9092 |
| InfluxDB            | `snore_events` time-series          | 8086 |
| MinIO (S3-compat.)  | Audio chunks + ML model artifacts   | 9000 / 9001 |
| Mobile App          | React Native + Expo (SDK 54)        | Expo Go |

> Both services *can* fall back to a local SQLite file if `DATABASE_URL`
> points at one, but the default `docker-compose up` flow wires up the full
> Postgres + Redis + Kafka + InfluxDB + MinIO stack described above.

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker Desktop | https://www.docker.com/products/docker-desktop |
| Node.js 18+ | https://nodejs.org |
| Expo Go app | Install on your Android/iOS phone from Play Store / App Store |

---

## Step 1 — Configure environment

```bash
cp .env.example .env
# then edit .env and set:
#   SECRET_KEY     — any 32+ random chars
#   INFLUXDB_TOKEN — any 32+ random chars (used as the Influx admin token)
```

Both services now refuse to start without a `SECRET_KEY` — no insecure default
is baked in. Docker Compose will fail loudly if `.env` is missing them.

---

## Step 2 — Start the Backend Services

```bash
docker-compose up --build
```

Wait until both services print `Application startup complete`.

Verify they are running:
- Auth Service:      http://localhost:8001/health
- Analytics Service: http://localhost:8002/health

Both should return `{"status": "ok"}`.

---

## Step 3 — Start the Mobile App

```bash
cd mobile
npm install
npx expo start
```

Expo will print a QR code in the terminal.

**On your phone:** Open the **Expo Go** app and scan the QR code.

> The app automatically detects your machine's IP address from Expo — no
> manual configuration needed for the dev flow. Your phone and laptop must
> be on the **same WiFi network**.
>
> For TestFlight / EAS / standalone builds you should override the API URLs
> via `EXPO_PUBLIC_AUTH_URL` and `EXPO_PUBLIC_ANALYTICS_URL` at build time,
> or set `extra.authUrl` / `extra.analyticsUrl` in `app.json`. The bundled
> Expo Go flow only works on the same LAN as the dev machine.

---

## Step 4 — Use the App

1. **Register** a new account (email + password)
2. Your account is automatically seeded with **30 days of realistic mock sleep data**
3. Explore:
   - **Home** — last night's Sleep Quality Score, weekly summary, insights
   - **Record** — tap to start a recording session (live loudness-based detection)
   - **History** — trend chart, session list with tap-through to full reports
   - **Profile** — account info, settings, logout

> The current "snoring vs breathing vs silence" classification is loudness-
> threshold based, not the CNN model described in the design docs. The CNN
> classifier (EfficientNet-B0 / TFLite) is on the roadmap.

---

## Project Structure

```
.
├── docker-compose.yml
├── .env.example
├── services/
│   ├── auth-service/          # FastAPI — register, login, JWT, user profile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── security.py
│   │   │   ├── redis_client.py
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       └── users.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── analytics-service/     # FastAPI — sessions, timeline, trends, insights
│       ├── app/
│       │   ├── main.py
│       │   ├── models.py
│       │   ├── scoring.py      ← grade / compute_score / make_timeline
│       │   ├── seed.py         ← 30-day mock data generator (uses scoring)
│       │   ├── patterns.py     ← pattern-based insight engine
│       │   ├── kafka_client.py
│       │   ├── influx_client.py
│       │   └── routes/
│       │       ├── sessions.py
│       │       ├── analytics.py
│       │       ├── insights.py
│       │       ├── lifestyle.py
│       │       └── ws.py
│       ├── Dockerfile
│       └── requirements.txt
└── mobile/                    # React Native + Expo
    ├── App.tsx
    └── src/
        ├── api/               # Axios clients for both services
        ├── store/             # Zustand auth store
        ├── navigation/        # Stack + Tab navigators (typed)
        ├── theme/             # Color system
        ├── components/        # ScoreRing, TimelineChart, TrendChart, InsightCard, StatCard
        └── screens/           # Onboarding, Login, Register, Home, Record, SessionDetail, History, Profile
```

---

## API Reference (Quick)

### Auth Service (port 8001)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create account → returns JWT |
| POST | `/auth/login` | Login → returns JWT (rate-limited 10/15min/IP) |
| POST | `/auth/refresh` | Rotate access token |
| POST | `/auth/logout` | Revoke refresh token |
| POST | `/auth/social/google` | Exchange a Google ID token for JWTs |
| POST | `/auth/forgot-password` | Generate reset token (logged in dev) |
| POST | `/auth/reset-password` | Consume reset token to set new password |
| GET  | `/users/me` | Get profile |
| PATCH | `/users/me` | Update profile fields |
| GET  | `/users/me/health-profile` | Read health questionnaire answers |
| PUT  | `/users/me/health-profile` | Update health questionnaire answers |

### Analytics Service (port 8002)
| Method | Path | Description |
|--------|------|-------------|
| GET  | `/sessions` | List all sessions |
| POST | `/sessions` | Start new session |
| POST | `/sessions/{id}/chunks` | Upload a 30-second chunk's summary stats |
| POST | `/sessions/{id}/end` | End session → computes score |
| GET  | `/sessions/{id}` | Get one session |
| GET  | `/analytics/timeline/{id}` | 5-min snoring timeline buckets |
| GET  | `/analytics/trends?period=30d` | Trend data (7d/30d/90d) |
| GET  | `/analytics/weekly-summary` | This week's summary |
| GET  | `/insights` | Personalised recommendations |
| PATCH | `/insights/{id}/read` | Mark an insight as read |
| GET  | `/lifestyle` | Recent lifestyle logs |
| POST | `/lifestyle` | Create/update a lifestyle log for a date |
| GET  | `/lifestyle/correlations` | Cross-reference logs with sleep scores |
| WSS  | `/ws` | Real-time chunk + session events |

Interactive API docs: http://localhost:8001/docs and http://localhost:8002/docs

---

## Troubleshooting

**App can't connect to services on physical device**
- Make sure phone and laptop are on the same WiFi
- Expo automatically uses your machine's LAN IP — check the Expo terminal output
- Firewall: allow ports 8001 and 8002 on your machine

**Docker build fails**
```bash
docker-compose down -v
docker-compose up --build
```

**Compose says `SECRET_KEY is required in .env`**
Copy `.env.example` to `.env` and fill in the required values. No defaults
ship for `SECRET_KEY` or `INFLUXDB_TOKEN` — both services refuse to start
with publicly-known fallback secrets.

**Expo module errors**
```bash
cd mobile
rm -rf node_modules
npm install
npx expo start --clear
```

---

## License

MIT — see [`LICENSE`](./LICENSE).
