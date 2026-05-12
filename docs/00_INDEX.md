# SleepSense — Architecture & Design Documentation
## Master Index

---

| # | Document | Contents |
|---|----------|----------|
| 01 | [High-Level Architecture](01_High_Level_Architecture.md) | System overview, component diagram, data flow, tech stack, NFRs, security |
| 02 | [Low-Level Design](02_Low_Level_Design.md) | Per-service LLD, internal flows, CNN model spec, analytics algorithms, project directory structure |
| 03 | [Database Schema](03_Database_Schema.md) | PostgreSQL tables, InfluxDB measurements, Redis structures, S3 layout, GDPR policy |
| 04 | [ML Pipeline Architecture](04_ML_Pipeline_Architecture.md) | Model catalog, feature engineering, Airflow training DAG, serving architecture, model monitoring, ethics |
| 05 | [API Design](05_API_Design.md) | All REST endpoints with request/response examples, WebSocket events, rate limits |
| 06 | [Scalability & Infrastructure](06_Scalability_and_Infrastructure.md) | Kubernetes config, CI/CD pipeline, Docker Compose, cost estimate, disaster recovery |
| 07 | [MVP Features & Stakeholder Deck](07_MVP_Features_Stakeholder_Deck.md) | 8 MVP features, phased roadmap, competitive analysis, demo script, investment ask |

---

## Quick Reference

### Technology Stack
- **Backend:** Python FastAPI (microservices)
- **Mobile:** React Native (iOS + Android)
- **ML:** PyTorch (training) + TFLite (on-device)
- **Database:** PostgreSQL + Redis + InfluxDB
- **Storage:** S3 / MinIO
- **Messaging:** Apache Kafka
- **Infra:** Docker + Kubernetes + GitHub Actions

### 3 Core ML Models
1. **Snore Classifier** — EfficientNet-B0 CNN, 4 classes, >92% F1
2. **Intensity Regressor** — XGBoost on MFCC features, 0–100 score
3. **Sleep Stage Estimator** — BiLSTM + Attention (Phase 2)

### MVP: 8 Features for Stakeholders
1. Sleep Recording (overnight background recording)
2. AI Snore Detection (CNN classifier)
3. Sleep Quality Score (0–100)
4. Snoring Timeline Visualization
5. Session History & Trends
6. Personalized Insights & Tips
7. User Health Profile & Lifestyle Logs
8. Bedtime Reminders & Goals

### Build Order (Recommended)
```
Week 1–2   → ML model training (Jupyter notebooks, your core strength)
Week 3–4   → Backend services (Auth + Audio Ingestion + ML Inference)
Week 5–6   → Analytics Service + API completions
Week 7–8   → Mobile app (recording + dashboard screens)
Week 9–10  → Integration testing + polish
Week 11–12 → Deploy to cloud + stakeholder demo
```
