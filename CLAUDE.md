# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

**SleepSense** is an AI-powered sleep/snoring analytics platform currently in the **documentation phase** — no source code exists yet. All design decisions are captured in `docs/`. Development follows the 12-week roadmap in `docs/07_MVP_Features_Stakeholder_Deck.md`.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Mobile | React Native + Expo (iOS + Android) |
| Web | React + TypeScript + Recharts |
| Backend | Python 3 + FastAPI (microservices) |
| ML Cloud | PyTorch + TorchServe |
| ML On-Device | TensorFlow Lite (INT8 quantized, <5MB) |
| Primary DB | PostgreSQL |
| Time-Series | InfluxDB (snoring events) |
| Cache | Redis |
| Object Storage | S3 / MinIO (audio files) |
| Message Broker | Apache Kafka (async ingestion → ML inference) |
| Containers | Docker + Kubernetes (EKS) |
| ML Ops | MLflow + Apache Airflow + Feast |

## Planned Commands

### Backend (Python / FastAPI)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload          # Run a single service
python -m pytest                       # All unit tests
python -m pytest tests/unit/test_X.py # Single test file
ruff check .                           # Lint
mypy app/                              # Type check
```

### Mobile (React Native)
```bash
npm install
npx expo start                         # Dev server
npx expo run:android / run:ios
npm test
npx tsc --noEmit                       # Type check
```

### Local Dev Stack
```bash
docker-compose up                      # Postgres, Redis, Kafka, InfluxDB, MinIO
docker-compose up postgres redis       # Subset for backend-only work
```

### ML Training
```bash
jupyter notebook ml-research/
airflow dags trigger snore_model_training
```

## Architecture

### Microservices (6 core services)

1. **Auth Service** — JWT + OAuth2 (Google, Apple), refresh tokens (30d TTL), RBAC
2. **Audio Ingestion Service** — Accepts 30s Opus chunks via multipart upload → stores in S3 → emits Kafka events
3. **ML Inference Service** — Consumes Kafka events → runs CNN classifier + XGBoost regressor → writes to InfluxDB
4. **Analytics Service** — Aggregates chunk results into session-level stats and sleep quality scores (0-100)
5. **Notification Service** — FCM/APNs push, SendGrid email, in-app alerts
6. **Insight Engine** — Rule-based + LLM recommendations from historical patterns

Each service uses a **4-layer pattern**: API routes → Service (business logic) → Repository (data access) → Domain (Pydantic models).

### Data Flow
```
Mobile mic → 30s Opus chunks → Audio Ingestion → S3 + Kafka
                                                       ↓
                                             ML Inference Service
                                             (CNN classifier → InfluxDB)
                                                       ↓
                                             Analytics Service
                                             (aggregates → PostgreSQL)
                                                       ↓
                                             Mobile dashboard
```

### ML Models

- **Snore Classifier** — EfficientNet-B0 fine-tuned on AudioSet; input: 128×128 mel spectrogram (3s window); 4 classes: snoring/breathing/silence/ambient; target F1 >92%
- **Intensity Regressor** — XGBoost on 40 MFCCs + RMS energy; output: 0-100 score; target MAE <5
- **Sleep Stage Estimator** (Phase 2) — BiLSTM + Attention on 30s audio + optional accelerometer

Dual serving: PyTorch (cloud, high accuracy) + TFLite quantized (on-device, offline/privacy mode).

### Database Assignments
- **PostgreSQL** — Users, sessions, insights, lifestyle logs, goals
- **InfluxDB** — `snore_events` measurement (per-chunk, time-tagged); `session_metrics` (5-min aggregations)
- **Redis** — JWT refresh tokens, rate limiting counters, session processing status cache
- **S3/MinIO** — Audio chunks at `{bucket}/{user_id}/{session_id}/chunk_*.opus`; ML model artifacts

## Key Design Decisions

- **30-second audio chunks** — Resilient to app crashes; enables real-time feedback; reduces mobile memory pressure
- **Kafka decoupling** — Ingestion and ML inference are independent; enables retry/replay without data loss
- **InfluxDB for events** — Purpose-built for high-cardinality time-series over PostgreSQL for snoring event streams
- **On-device TFLite option** — Audio never leaves device; satisfies privacy-conscious users
- **JWT 15-min TTL** — Short-lived access tokens; refresh token rotation on each use

## API Overview

Base URL: `https://api.sleepsense.app/v1`

Key flows:
- Session lifecycle: `POST /sessions` → `POST /sessions/{id}/chunks` (repeat) → `POST /sessions/{id}/end`
- Auth: `POST /auth/login` returns access token (15m) + refresh token (30d)
- Real-time progress: `WSS /ws` WebSocket for chunk processing updates
- Error format: RFC 7807 Problem Details JSON

Full endpoint reference: `docs/05_API_Design.md`

## Documentation Index

| File | Contents |
|------|----------|
| `docs/01_High_Level_Architecture.md` | System components, data flows, NFRs, security |
| `docs/02_Low_Level_Design.md` | Per-service LLD, CNN spec, directory structure |
| `docs/03_Database_Schema.md` | All table definitions, InfluxDB/Redis/S3 schemas |
| `docs/04_ML_Pipeline_Architecture.md` | Model catalog, Airflow DAG, feature engineering, drift monitoring |
| `docs/05_API_Design.md` | All REST + WebSocket endpoints with examples |
| `docs/06_Scalability_and_Infrastructure.md` | K8s config, CI/CD pipeline, Docker Compose, cost estimates |
| `docs/07_MVP_Features_Stakeholder_Deck.md` | 8 MVP features, 12-week build roadmap, competitive analysis |
