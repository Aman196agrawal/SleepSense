# High-Level Architecture (HLA)
## SleepSense — AI-Powered Sleep & Snoring Analytics Platform

---

## 1. System Vision

SleepSense is a multi-platform, AI-driven application that records, analyzes, and provides actionable insights on sleep quality and snoring patterns. The system is designed as a cloud-native, microservices-based architecture capable of scaling from a single-user MVP to millions of concurrent users.

---

## 2. Architecture Style

| Concern            | Choice                        | Reason                                              |
|--------------------|-------------------------------|-----------------------------------------------------|
| Service topology   | Microservices                 | Independent scaling, deployment, and fault isolation|
| Communication      | REST (sync) + Event Bus (async)| REST for CRUD, events for ML pipeline & notifications|
| Data strategy      | Polyglot persistence          | Right DB for each workload                          |
| Deployment         | Containerized (Docker + K8s)  | Cloud-agnostic, auto-scaling                        |
| ML serving         | Dedicated inference service   | GPU-isolated, versioned model rollout               |
| Security           | Zero-trust, JWT + OAuth2      | Stateless auth, fine-grained permissions            |

---

## 3. High-Level Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                                │
│                                                                      │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐   │
│   │  Mobile App  │   │   Web App    │   │  Wearable / IoT SDK  │   │
│   │ iOS/Android  │   │   (React)    │   │  (Future: WatchOS)   │   │
│   │(React Native)│   │              │   │                      │   │
│   └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘   │
└──────────┼─────────────────┼──────────────────────┼────────────────┘
           │                 │                       │
           └─────────────────┴───────────────────────┘
                                    │ HTTPS / WSS
┌───────────────────────────────────▼─────────────────────────────────┐
│                          API GATEWAY LAYER                           │
│                                                                      │
│   ┌─────────────────────────────────────────────────────────────┐   │
│   │         API Gateway (Kong / AWS API Gateway / Nginx)         │   │
│   │   Rate Limiting │ Auth Verification │ SSL Termination        │   │
│   │   Load Balancing │ Request Routing │ CORS │ Logging          │   │
│   └────────────────────────────┬────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                        MICROSERVICES LAYER                           │
│                                                                      │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐ ┌───────────┐  │
│  │    Auth     │ │    User      │ │    Session    │ │  Audio    │  │
│  │   Service   │ │   Service    │ │    Service    │ │ Ingestion │  │
│  │  (JWT/OAuth)│ │(Profile/Prefs│ │(Sleep Records)│ │ Service   │  │
│  └─────────────┘ └──────────────┘ └───────────────┘ └─────┬─────┘  │
│                                                             │        │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────┐       │        │
│  │  Analytics  │ │  ML/AI       │ │ Notification  │       │        │
│  │   Service   │ │  Inference   │ │   Service     │       │        │
│  │(Insights/DB)│ │   Service    │ │(Push/Email)   │       │        │
│  └──────┬──────┘ └──────┬───────┘ └───────────────┘       │        │
│         │               │◄────────────────────────────────┘        │
└─────────┼───────────────┼────────────────────────────────────────── ┘
          │               │
          │        ┌──────▼──────────────────┐
          │        │     MESSAGE BROKER       │
          │        │  (Apache Kafka / RabbitMQ│
          │        │  audio.uploaded topic    │
          │        │  analysis.complete topic │
          │        │  insight.ready topic     │
          │        └──────┬──────────────────┘
          │               │
┌─────────▼───────────────▼───────────────────────────────────────────┐
│                          DATA LAYER                                  │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │  PostgreSQL  │ │    Redis     │ │  S3 / Blob   │ │ InfluxDB  │  │
│  │(Users,Session│ │  (Cache,     │ │   Storage    │ │(Time-series│  │
│  │ Analytics)  │ │  Sessions,   │ │(Audio Files, │ │ snore events│ │
│  │             │ │  Rate Limits)│ │  Spectrograms│ │ metrics)   │  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────────┐
│                         ML PLATFORM LAYER                            │
│                                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐  │
│  │  Model       │ │  Feature     │ │  Training    │ │  Model    │  │
│  │  Registry    │ │  Store       │ │  Pipeline    │ │  Monitor  │  │
│  │ (MLflow)     │ │ (Feast)      │ │ (Airflow)    │ │(Evidently)│  │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow — Sleep Recording Session

```
User Starts Recording
        │
        ▼
Mobile App records audio (chunks every 30s)
        │
        ▼
Audio uploaded to Audio Ingestion Service via chunked multipart POST
        │
        ├──► Audio File stored in S3 (raw .wav / .m4a)
        │
        ▼
Kafka Event: "audio.chunk.uploaded" (session_id, chunk_id, s3_path)
        │
        ▼
ML Inference Service consumes event:
  1. Load audio from S3
  2. Preprocess → Mel Spectrogram
  3. Run CNN classifier → {snoring, breathing, silence, ambient}
  4. Score snore intensity (0–100)
  5. Store results → InfluxDB (timestamped events) + PostgreSQL
        │
        ▼
Kafka Event: "analysis.complete" (session_id, chunk_id, results)
        │
        ├──► Analytics Service aggregates session stats
        │
        ▼
User ends session → Analytics Service computes:
  - Total sleep duration
  - Snore score (0–100)
  - Snore frequency (events/hour)
  - Noise timeline
  - Comparative trend (vs. previous nights)
        │
        ▼
Insight Engine generates personalized recommendations
        │
        ▼
Push notification to user: "Your sleep report is ready"
        │
        ▼
Dashboard renders analytics
```

---

## 5. Key Architecture Decisions

### 5.1 On-Device vs. Cloud ML
| Mode            | When Used                                  | Benefit                       |
|-----------------|--------------------------------------------|-------------------------------|
| Cloud inference | Default (WiFi available)                   | Heavy model, highest accuracy |
| On-device (TFLite) | Offline / poor connectivity             | Privacy, no data upload needed|

### 5.2 Audio Chunking Strategy
- Record in **30-second chunks** rather than one continuous file
- Enables real-time processing during the session
- Resilient to app crashes — partial data is recoverable
- Reduces memory pressure on mobile devices

### 5.3 Event-Driven Architecture
- Audio ingestion is **decoupled** from ML inference via Kafka
- ML service can scale independently under heavy load
- Supports retry/replay if ML service is temporarily down
- Analytics service reacts to events, not polling

---

## 6. Non-Functional Requirements

| NFR                | Target                                      |
|--------------------|---------------------------------------------|
| Availability       | 99.9% uptime (3 nines SLA)                  |
| Latency            | API response < 200ms (P95)                  |
| ML inference       | < 3 seconds per 30s audio chunk             |
| Storage            | ~50MB per 8-hour session (compressed audio) |
| Concurrent users   | 10,000 simultaneous sessions (v1 target)    |
| Data retention     | 12 months of sleep history per user         |
| HIPAA-readiness    | Encrypted at rest + in transit, audit logs  |

---

## 7. Security Architecture

```
Client → TLS 1.3 → API Gateway → JWT Validation → Service
                                        │
                            OAuth2 (Google/Apple Sign-In)
                                        │
                            RBAC (user / admin / researcher roles)
                                        │
                            Audio encrypted in S3 (AES-256)
                                        │
                            PII anonymization for analytics
```

---

## 8. Technology Stack Summary

| Layer              | Technology                    |
|--------------------|-------------------------------|
| Mobile             | React Native (Expo)           |
| Web Frontend       | React + TypeScript + Recharts |
| API Gateway        | Nginx / Kong                  |
| Backend Services   | Python (FastAPI)              |
| ML Framework       | PyTorch + TorchServe          |
| On-device ML       | TensorFlow Lite               |
| Message Broker     | Apache Kafka                  |
| Primary DB         | PostgreSQL                    |
| Cache              | Redis                         |
| Time-series DB     | InfluxDB                      |
| Object Storage     | AWS S3 / MinIO (self-hosted)  |
| ML Ops             | MLflow + Apache Airflow       |
| Container Runtime  | Docker + Kubernetes (K8s)     |
| CI/CD              | GitHub Actions                |
| Monitoring         | Prometheus + Grafana          |
| Logging            | ELK Stack (Elasticsearch)     |
