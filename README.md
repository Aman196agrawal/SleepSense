# Product Gem — Sample Build

A full-stack running Android sample of the SleepSense product, renamed **Product Gem** for showcase.

## What's Running

| Layer | Technology | Port |
|-------|-----------|------|
| Auth Service | Python FastAPI + SQLite | 8001 |
| Analytics Service | Python FastAPI + SQLite + mock data | 8002 |
| Mobile App | React Native + Expo | Expo Go |

---

## Prerequisites

| Tool | Install |
|------|---------|
| Docker Desktop | https://www.docker.com/products/docker-desktop |
| Node.js 18+ | https://nodejs.org |
| Expo Go app | Install on your Android/iOS phone from Play Store / App Store |

---

## Step 1 — Start the Backend Services

```bash
# From the root of this repo:
docker-compose up --build
```

Wait until you see both services print `Application startup complete`.

Verify they are running:
- Auth Service:      http://localhost:8001/health
- Analytics Service: http://localhost:8002/health

Both should return `{"status": "ok"}`.

---

## Step 2 — Start the Mobile App

```bash
cd mobile
npm install
npx expo start
```

Expo will print a QR code in the terminal.

**On your phone:** Open the **Expo Go** app and scan the QR code.

> The app automatically detects your machine's IP address — no manual configuration needed.
> Make sure your phone and laptop are on the **same WiFi network**.

---

## Step 3 — Use the App

1. **Register** a new account (email + password)
2. Your account is automatically seeded with **30 days of realistic mock sleep data**
3. Explore:
   - **Home** — last night's Sleep Quality Score, weekly summary, insights
   - **Record** — tap to simulate a recording session (shows live sound detection)
   - **History** — trend chart, session list with tap-through to full reports
   - **Profile** — account info, settings, logout

---

## Project Structure

```
SnoreLab/
├── docker-compose.yml
├── services/
│   ├── auth-service/          # FastAPI — register, login, JWT, user profile
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── security.py
│   │   │   └── routes/
│   │   │       ├── auth.py
│   │   │       └── users.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── analytics-service/     # FastAPI — sessions, timeline, trends, insights + seeder
│       ├── app/
│       │   ├── main.py
│       │   ├── models.py
│       │   ├── seed.py        ← 30-day mock data generator
│       │   └── routes/
│       │       ├── sessions.py
│       │       ├── analytics.py
│       │       └── insights.py
│       ├── Dockerfile
│       └── requirements.txt
└── mobile/                    # React Native + Expo
    ├── App.tsx
    └── src/
        ├── api/               # Axios clients for both services
        ├── store/             # Zustand auth store
        ├── navigation/        # Stack + Tab navigators
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
| POST | `/auth/login` | Login → returns JWT |
| POST | `/auth/refresh` | Rotate access token |
| GET | `/users/me` | Get profile |

### Analytics Service (port 8002)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/sessions` | List all sessions |
| POST | `/sessions` | Start new session |
| POST | `/sessions/{id}/end` | End session → computes score |
| GET | `/analytics/timeline/{id}` | 5-min snoring timeline buckets |
| GET | `/analytics/trends?period=30d` | Trend data (7d/30d/90d) |
| GET | `/analytics/weekly-summary` | This week's summary |
| GET | `/insights` | Personalized recommendations |

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

**Expo module errors**
```bash
cd mobile
rm -rf node_modules
npm install
npx expo start --clear
```
