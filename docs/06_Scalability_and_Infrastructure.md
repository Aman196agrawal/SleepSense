# Scalability & Infrastructure Architecture
## SleepSense — Cloud-Native Deployment Design

---

## 1. Scalability Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCALABILITY DIMENSIONS                        │
│                                                                  │
│  Horizontal Scaling   → Add more service replicas (K8s HPA)    │
│  Vertical Scaling     → Larger instance for ML GPU workloads    │
│  Database Scaling     → Read replicas + connection pooling       │
│  Storage Scaling      → S3 infinitely scalable by design         │
│  CDN Caching          → Static assets + audio previews cached   │
│  Queue-based decoupling → Kafka absorbs upload spikes           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure Diagram (Cloud)

```
                    ┌─────────────────────┐
                    │    CloudFlare CDN    │
                    │  (DDoS, WAF, Cache) │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   Load Balancer     │
                    │  (AWS ALB / GCP LB) │
                    └──────────┬──────────┘
                               │
              ┌────────────────┴─────────────────┐
              ▼                                   ▼
   ┌──────────────────┐               ┌──────────────────┐
   │  API Gateway     │               │  WebSocket       │
   │  Cluster         │               │  Gateway         │
   │  (3+ replicas)   │               │  (2+ replicas)   │
   └────────┬─────────┘               └────────┬─────────┘
            │                                  │
            └──────────────┬───────────────────┘
                           │
         ┌─────────────────▼──────────────────────────┐
         │          KUBERNETES CLUSTER                  │
         │                                              │
         │  Namespace: sleepsense-prod                  │
         │                                              │
         │  ┌─────────────┐  ┌─────────────────────┐   │
         │  │ auth-svc    │  │  user-svc           │   │
         │  │ 2 replicas  │  │  2 replicas          │   │
         │  └─────────────┘  └─────────────────────┘   │
         │                                              │
         │  ┌─────────────┐  ┌─────────────────────┐   │
         │  │ audio-svc   │  │  analytics-svc      │   │
         │  │ 3 replicas  │  │  3 replicas          │   │
         │  │ (CPU-heavy) │  │                     │   │
         │  └─────────────┘  └─────────────────────┘   │
         │                                              │
         │  ┌─────────────────────────────────────────┐ │
         │  │      ml-inference-svc                   │ │
         │  │  2 GPU replicas (NVIDIA T4)             │ │
         │  │  Auto-scales 2→8 based on Kafka lag     │ │
         │  └─────────────────────────────────────────┘ │
         │                                              │
         │  ┌─────────────┐  ┌─────────────────────┐   │
         │  │ notif-svc   │  │  insight-engine     │   │
         │  │ 2 replicas  │  │  2 replicas          │   │
         │  └─────────────┘  └─────────────────────┘   │
         └───────────────────┬────────────────────────--┘
                             │
         ┌───────────────────▼──────────────────────────┐
         │              MANAGED SERVICES                  │
         │                                               │
         │  ┌──────────────┐  ┌──────────────────────┐  │
         │  │  RDS          │  │  ElastiCache Redis   │  │
         │  │  PostgreSQL   │  │  (cluster mode)      │  │
         │  │  (Multi-AZ)   │  │  3 shards            │  │
         │  │  1 primary    │  └──────────────────────┘  │
         │  │  2 replicas   │                            │
         │  └──────────────┘  ┌──────────────────────┐  │
         │                    │  MSK (Kafka)         │  │
         │  ┌──────────────┐  │  3 brokers, 3 AZs   │  │
         │  │  InfluxDB     │  └──────────────────────┘  │
         │  │  Cloud        │                            │
         │  │  (or self-   │  ┌──────────────────────┐  │
         │  │  hosted on   │  │  S3 + CloudFront     │  │
         │  │  K8s)        │  │  (audio storage)     │  │
         │  └──────────────┘  └──────────────────────┘  │
         └───────────────────────────────────────────────┘
```

---

## 3. Kubernetes Resource Configuration

### HPA (Horizontal Pod Autoscaler) — Audio Ingestion
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: audio-ingestion-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: audio-ingestion-service
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### HPA — ML Inference (Kafka-based scaling)
```yaml
# Uses KEDA (Kubernetes Event-Driven Autoscaling)
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: ml-inference-scaler
spec:
  scaleTargetRef:
    name: ml-inference-service
  minReplicaCount: 2
  maxReplicaCount: 8
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: ml-inference-group
        topic: audio.chunk.uploaded
        lagThreshold: "100"          # scale up if lag > 100 messages
```

---

## 4. Multi-Environment Strategy

| Environment | Purpose                          | Infrastructure          |
|-------------|----------------------------------|-------------------------|
| local       | Developer laptop                 | Docker Compose          |
| dev         | Integration testing              | K8s (single node)       |
| staging     | Pre-production validation        | K8s (scaled-down prod)  |
| prod        | Live users                       | K8s (full multi-AZ)     |

### Docker Compose (Local Dev)
```yaml
version: '3.9'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: sleepsense
      POSTGRES_PASSWORD: devpassword
    ports: ["5432:5432"]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    depends_on: [zookeeper]

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0

  influxdb:
    image: influxdb:2.7
    ports: ["8086:8086"]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]

  auth-service:
    build: ./services/auth-service
    ports: ["8001:8000"]
    depends_on: [postgres, redis]
    environment:
      DATABASE_URL: postgresql://postgres:devpassword@postgres:5432/sleepsense
      REDIS_URL: redis://redis:6379

  ml-inference-service:
    build: ./services/ml-inference-service
    depends_on: [kafka, minio]
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]    # GPU passthrough if available
```

---

## 5. CI/CD Pipeline (GitHub Actions)

```
Developer pushes to feature branch
        │
        ▼
[PR Checks — parallel]
  ├── Lint (ruff, eslint)
  ├── Type check (mypy, tsc)
  ├── Unit tests
  └── Security scan (trivy, bandit)
        │ All pass
        ▼
Code review + PR merged to main
        │
        ▼
[Build Pipeline]
  ├── Build Docker images
  ├── Run integration tests (docker-compose)
  ├── Run ML model validation (if model files changed)
  └── Push images to ECR (tagged with git SHA)
        │
        ▼
[Deploy to Staging]
  ├── Helm upgrade sleepsense-staging
  ├── Run E2E tests (Playwright)
  └── Run load test (k6, 100 virtual users)
        │ Pass
        ▼
[Deploy to Production]
  ├── Blue-Green deployment (zero downtime)
  ├── Smoke tests
  ├── Monitor error rate for 10 minutes
  └── Auto-rollback if error rate > 1%
```

---

## 6. Observability Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                     OBSERVABILITY LAYER                          │
│                                                                  │
│  METRICS (Prometheus + Grafana)                                  │
│  ├── Service health (request rate, error rate, latency)          │
│  ├── ML metrics (inference time, queue depth, accuracy)          │
│  ├── Business metrics (DAU, sessions/day, avg quality score)     │
│  └── Infrastructure (CPU, memory, disk, network)                 │
│                                                                  │
│  LOGGING (ELK Stack)                                             │
│  ├── Structured JSON logs from all services                      │
│  ├── Correlation IDs for request tracing                         │
│  └── Kibana dashboards for log analysis                          │
│                                                                  │
│  TRACING (Jaeger / OpenTelemetry)                                │
│  └── Distributed trace: API Gateway → Service → DB → Kafka       │
│                                                                  │
│  ALERTING (PagerDuty / Slack)                                    │
│  ├── P1: API error rate > 5% → page on-call immediately          │
│  ├── P2: ML inference lag > 5 min → alert #ml-ops channel        │
│  └── P3: Daily digest of business metrics anomalies              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Cost Estimation (Monthly, ~10k DAU)

| Resource                      | Estimated Cost / Month  |
|-------------------------------|-------------------------|
| EKS Cluster (3 nodes m5.large)| $300                    |
| RDS PostgreSQL (db.t3.medium) | $80                     |
| ElastiCache Redis (cache.t3)  | $50                     |
| MSK Kafka (kafka.t3.small)    | $120                    |
| S3 Storage (5TB audio)        | $115                    |
| CloudFront CDN                | $30                     |
| ML GPU instances (g4dn.xlarge)| $400                    |
| InfluxDB Cloud                | $50                     |
| Misc (logs, monitoring, email)| $80                     |
| **Total**                     | **~$1,225/month**       |

> For MVP (100 users), use Railway / Render / Fly.io + managed PostgreSQL → ~$30–50/month

---

## 8. Disaster Recovery

| Metric             | Target                                              |
|--------------------|-----------------------------------------------------|
| RTO (Recovery Time)| < 1 hour for P1 incidents                          |
| RPO (Data Loss)    | < 5 minutes (PostgreSQL WAL streaming replication) |
| Audio backup       | S3 Cross-Region Replication (async, ~15s lag)      |
| DB backup          | Daily automated snapshots + continuous WAL          |
| Runbook location   | docs/runbooks/ in this repository                   |
