"""
SleepSense Architecture Diagram Generator
Generates PNG images for all architecture diagrams from the docs.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe
import numpy as np
import os

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

COLORS = {
    "client":    "#4A90D9",
    "gateway":   "#7B68EE",
    "service":   "#2ECC71",
    "data":      "#E67E22",
    "ml":        "#E74C3C",
    "kafka":     "#F39C12",
    "bg":        "#F8F9FA",
    "arrow":     "#34495E",
    "header":    "#2C3E50",
    "white":     "#FFFFFF",
    "infra":     "#16A085",
    "cicd":      "#8E44AD",
    "obs":       "#1ABC9C",
    "light_blue":"#D6EAF8",
    "light_green":"#D5F5E3",
    "light_orange":"#FAE5D3",
    "light_purple":"#E8DAEF",
    "light_red":  "#FADBD8",
}

def rounded_box(ax, x, y, w, h, color, text, fontsize=9, text_color="white",
                radius=0.03, alpha=1.0, bold=False, wrap=False):
    box = FancyBboxPatch((x, y), w, h,
                          boxstyle=f"round,pad=0.01,rounding_size={radius}",
                          facecolor=color, edgecolor="white",
                          linewidth=1.5, alpha=alpha, zorder=3)
    ax.add_patch(box)
    weight = "bold" if bold else "normal"
    ax.text(x + w/2, y + h/2, text, ha="center", va="center",
            fontsize=fontsize, color=text_color, fontweight=weight,
            wrap=wrap, zorder=4, multialignment="center")

def arrow(ax, x1, y1, x2, y2, color="#34495E", lw=1.5, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=color,
                                lw=lw, mutation_scale=15),
                zorder=5)
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx+0.01, my+0.01, label, fontsize=7, color=color, zorder=6)

def section_label(ax, x, y, w, h, text, color):
    box = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.005,rounding_size=0.02",
                          facecolor=color, edgecolor=color,
                          linewidth=2, alpha=0.15, zorder=2)
    ax.add_patch(box)
    ax.text(x + 0.01, y + h - 0.015, text, ha="left", va="top",
            fontsize=8, color=color, fontweight="bold", zorder=3)


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 1 — High-Level Architecture
# ─────────────────────────────────────────────────────────────────────────────
def diagram_hla():
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])
    ax.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.975, "SleepSense — High-Level Architecture",
            ha="center", va="top", fontsize=16, fontweight="bold",
            color=COLORS["header"])

    # ── CLIENT LAYER ──────────────────────────────────────────────────────────
    section_label(ax, 0.02, 0.82, 0.96, 0.13, "CLIENT LAYER", COLORS["client"])
    for i, (txt, sub) in enumerate([
        ("Mobile App", "iOS / Android\nReact Native"),
        ("Web App", "React + TypeScript"),
        ("Wearable SDK", "Future: WatchOS"),
    ]):
        x = 0.10 + i * 0.32
        rounded_box(ax, x, 0.845, 0.22, 0.07, COLORS["client"], f"{txt}\n{sub}",
                    fontsize=8.5, bold=True)

    # arrows from clients down
    for x in [0.21, 0.53, 0.85]:
        arrow(ax, x, 0.845, x, 0.805, label="" if x != 0.53 else "HTTPS/WSS")

    # ── API GATEWAY ───────────────────────────────────────────────────────────
    section_label(ax, 0.02, 0.71, 0.96, 0.09, "API GATEWAY", COLORS["gateway"])
    rounded_box(ax, 0.08, 0.725, 0.84, 0.06, COLORS["gateway"],
                "API Gateway (Kong / Nginx)\n"
                "Rate Limiting  |  Auth Verification  |  SSL Termination  |  "
                "Load Balancing  |  Request Routing  |  CORS  |  Logging",
                fontsize=8)
    arrow(ax, 0.5, 0.725, 0.5, 0.685)

    # ── MICROSERVICES ─────────────────────────────────────────────────────────
    section_label(ax, 0.02, 0.50, 0.96, 0.18, "MICROSERVICES LAYER", COLORS["service"])
    svcs = [
        ("Auth Service", "JWT / OAuth2"),
        ("User Service", "Profile / Prefs"),
        ("Session Service", "Sleep Records"),
        ("Audio Ingestion", "S3 + Kafka emit"),
        ("ML Inference", "CNN + XGBoost"),
        ("Analytics", "Insights / DB"),
        ("Notifications", "FCM / APNs"),
        ("Insight Engine", "Rules + LLM"),
    ]
    cols = 4
    for idx, (name, sub) in enumerate(svcs):
        row = idx // cols
        col = idx % cols
        bx = 0.06 + col * 0.235
        by = 0.62 - row * 0.105
        rounded_box(ax, bx, by, 0.20, 0.085, COLORS["service"],
                    f"{name}\n{sub}", fontsize=8)

    # arrow from gateway to services
    arrow(ax, 0.5, 0.685, 0.5, 0.665)

    # ── KAFKA ─────────────────────────────────────────────────────────────────
    section_label(ax, 0.28, 0.38, 0.44, 0.10, "MESSAGE BROKER", COLORS["kafka"])
    rounded_box(ax, 0.30, 0.395, 0.40, 0.07, COLORS["kafka"],
                "Apache Kafka\naudio.chunk.uploaded  |  analysis.complete  |  insight.ready",
                fontsize=8.5, bold=True)
    arrow(ax, 0.5, 0.50, 0.5, 0.465)
    arrow(ax, 0.5, 0.395, 0.5, 0.35)

    # ── DATA LAYER ────────────────────────────────────────────────────────────
    section_label(ax, 0.02, 0.20, 0.96, 0.14, "DATA LAYER", COLORS["data"])
    dbs = [
        ("PostgreSQL", "Users, Sessions\nAnalytics"),
        ("Redis", "Cache\nRate Limits\nJWT Tokens"),
        ("S3 / MinIO", "Audio Chunks\nSpectrograms\nML Artifacts"),
        ("InfluxDB", "Time-Series\nSnore Events\nSession Metrics"),
    ]
    for i, (name, sub) in enumerate(dbs):
        bx = 0.06 + i * 0.235
        rounded_box(ax, bx, 0.215, 0.20, 0.09, COLORS["data"],
                    f"{name}\n{sub}", fontsize=8)

    # ── ML PLATFORM ───────────────────────────────────────────────────────────
    section_label(ax, 0.02, 0.04, 0.96, 0.13, "ML PLATFORM LAYER", COLORS["ml"])
    ml_comps = [
        ("Model Registry", "MLflow"),
        ("Feature Store", "Feast"),
        ("Training Pipeline", "Apache Airflow"),
        ("Model Monitor", "Evidently AI"),
    ]
    for i, (name, sub) in enumerate(ml_comps):
        bx = 0.06 + i * 0.235
        rounded_box(ax, bx, 0.055, 0.20, 0.075, COLORS["ml"],
                    f"{name}\n{sub}", fontsize=8)

    arrow(ax, 0.5, 0.20, 0.5, 0.135)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "01_High_Level_Architecture.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 2 — Data Flow (Sleep Recording Session)
# ─────────────────────────────────────────────────────────────────────────────
def diagram_data_flow():
    fig, ax = plt.subplots(figsize=(10, 16))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.985, "SleepSense — Data Flow: Sleep Recording Session",
            ha="center", va="top", fontsize=14, fontweight="bold",
            color=COLORS["header"])

    steps = [
        (COLORS["client"],  "User Starts Recording",                      "Mobile microphone begins capture"),
        (COLORS["client"],  "30-Second Audio Chunks",                     "React Native records & buffers chunks"),
        (COLORS["gateway"], "Audio Ingestion Service",                    "POST /sessions/{id}/chunks  (multipart)"),
        (COLORS["data"],    "S3 Storage",                                 "s3://sleepsense-audio/{user}/{session}/chunk_N.opus"),
        (COLORS["kafka"],   "Kafka Event: audio.chunk.uploaded",          "{chunk_id, session_id, s3_key, timestamp}"),
        (COLORS["ml"],      "ML Inference Service",                       "① Load audio  ② Mel Spectrogram\n③ CNN Classifier  ④ Intensity Regressor"),
        (COLORS["data"],    "InfluxDB + PostgreSQL",                      "snore_events (time-tagged) + chunk result"),
        (COLORS["kafka"],   "Kafka Event: analysis.complete",             "{session_id, chunk_id, snore_ratio, avg_intensity}"),
        (COLORS["service"], "Analytics Service",                          "Aggregates session stats:\nsnore score, frequency, timeline"),
        (COLORS["service"], "Insight Engine",                             "Rule-based + LLM recommendations"),
        (COLORS["service"], "Notification Service",                       "Push: 'Your sleep report is ready'"),
        (COLORS["client"],  "Mobile Dashboard",                           "Renders charts, score, insights"),
    ]

    n = len(steps)
    y_start = 0.945
    step_h = 0.065
    gap = 0.008

    for i, (color, title, detail) in enumerate(steps):
        y = y_start - i * (step_h + gap)
        rounded_box(ax, 0.10, y - step_h, 0.80, step_h,
                    color, f"{title}\n{detail}",
                    fontsize=8.5, bold=False)
        if i < n - 1:
            arrow(ax, 0.5, y - step_h, 0.5, y - step_h - gap - 0.001,
                  color=COLORS["arrow"])

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "02_Data_Flow_Session.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 3 — Microservice Layered Architecture
# ─────────────────────────────────────────────────────────────────────────────
def diagram_microservice_layers():
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.97, "SleepSense — Microservice Internal Layered Architecture",
            ha="center", va="top", fontsize=14, fontweight="bold",
            color=COLORS["header"])

    layers = [
        (COLORS["client"],  "API / Controller Layer",    "FastAPI routes, request validation, Pydantic schemas"),
        (COLORS["gateway"], "Service Layer",              "Business logic, orchestration, use-case handlers"),
        (COLORS["service"], "Repository Layer",           "DB queries, data-access objects (SQLAlchemy / aiomysql)"),
        (COLORS["data"],    "Domain Layer",               "Pydantic models, enums, constants, value objects"),
        (COLORS["ml"],      "Infrastructure Layer",       "DB connections, S3 client, Kafka producer/consumer, Redis"),
    ]

    y = 0.86
    h = 0.11
    gap = 0.02
    for color, name, detail in layers:
        rounded_box(ax, 0.08, y, 0.84, h, color,
                    f"{name}\n{detail}", fontsize=9.5, bold=True)
        if y > 0.2:
            arrow(ax, 0.5, y, 0.5, y - gap, color=COLORS["arrow"])
        y -= h + gap

    # bidirectional note
    ax.text(0.5, 0.08,
            "Each layer only talks to the layer directly below it  ·  "
            "Dependencies flow downward  ·  No layer skipping",
            ha="center", va="center", fontsize=9, color="#555",
            style="italic")

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "03_Microservice_Layer_Architecture.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 4 — ML Pipeline Architecture
# ─────────────────────────────────────────────────────────────────────────────
def diagram_ml_pipeline():
    fig, ax = plt.subplots(figsize=(16, 11))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.985, "SleepSense — ML System Architecture",
            ha="center", va="top", fontsize=15, fontweight="bold",
            color=COLORS["header"])

    # ── TOP: 3 pipelines ─────────────────────────────────────────────────────
    pipes = [
        (0.04, "Data Pipeline",    COLORS["data"],    "Raw audio ingestion\nLabel validation\nDataset versioning"),
        (0.37, "Training Pipeline", COLORS["service"], "Airflow DAG\nFeature engineering\nModel training / eval"),
        (0.70, "Serving Pipeline",  COLORS["ml"],      "Kafka consumer\nInference workers\nResult aggregation"),
    ]
    for x, title, color, detail in pipes:
        rounded_box(ax, x, 0.80, 0.28, 0.14, color,
                    f"{title}\n\n{detail}", fontsize=9, bold=True)

    arrow(ax, 0.32, 0.87, 0.37, 0.87, label="features →")
    arrow(ax, 0.65, 0.87, 0.70, 0.87, label="model →")

    # ── MIDDLE ROW: stores ───────────────────────────────────────────────────
    stores = [
        (0.04, "Feature Store\n(Feast)", COLORS["data"]),
        (0.37, "Experiment Tracking\n(MLflow)", COLORS["service"]),
        (0.70, "Model Registry\n(MLflow)", COLORS["ml"]),
    ]
    for x, label, color in stores:
        rounded_box(ax, x, 0.635, 0.28, 0.09, color, label, fontsize=9)
    for x in [0.18, 0.51, 0.84]:
        arrow(ax, x, 0.80, x, 0.725)

    # ── MODEL CATALOG ─────────────────────────────────────────────────────────
    section_label(ax, 0.02, 0.36, 0.96, 0.24, "MODEL CATALOG", COLORS["ml"])
    models = [
        ("Snore Classifier\n(Primary)",
         "EfficientNet-B0\nInput: 128×128 Mel Spec\nOutput: 4 classes\nTarget F1 > 92%",
         COLORS["ml"]),
        ("Intensity Regressor",
         "XGBoost\nInput: 40 MFCCs + RMS\nOutput: 0–100 score\nTarget MAE < 5",
         "#C0392B"),
        ("Sleep Stage Estimator\n(Phase 2)",
         "BiLSTM + Attention\nInput: 30s audio\n+ accelerometer\nOutput: Awake/Light/Deep/REM",
         "#9B59B6"),
        ("Apnea Risk Screener\n(Phase 2)",
         "Binary Classifier\nInput: 7-night history\nOutput: Low/Med/High\nNOT a medical diagnosis",
         "#8E44AD"),
    ]
    for i, (name, detail, color) in enumerate(models):
        bx = 0.04 + i * 0.24
        rounded_box(ax, bx, 0.375, 0.22, 0.19, color,
                    f"{name}\n\n{detail}", fontsize=7.5)

    # ── AIRFLOW DAG ───────────────────────────────────────────────────────────
    section_label(ax, 0.02, 0.09, 0.96, 0.245,
                  "TRAINING DAG (Apache Airflow)", COLORS["kafka"])
    dag_tasks = [
        "data_validation",
        "feature_engineering",
        "train_classifier",
        "evaluate_classifier",
        "train_intensity_regressor",
        "model_registration",
        "export_tflite",
    ]
    for i, task in enumerate(dag_tasks):
        bx = 0.03 + i * 0.136
        rounded_box(ax, bx, 0.115, 0.12, 0.20, COLORS["kafka"],
                    task.replace("_", "\n"), fontsize=7.5)
        if i < len(dag_tasks) - 1:
            arrow(ax, bx + 0.12, 0.215, bx + 0.136, 0.215)

    # ── MLOPS banner ─────────────────────────────────────────────────────────
    rounded_box(ax, 0.04, 0.025, 0.92, 0.055, "#2C3E50",
                "MLOps / Monitoring:  Data Drift (Evidently)  |  "
                "Model Performance (weekly spot-check)  |  "
                "Alerts (PagerDuty)  |  Auto-retraining trigger",
                fontsize=8.5)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "04_ML_Pipeline_Architecture.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 5 — ML Inference Service Detail
# ─────────────────────────────────────────────────────────────────────────────
def diagram_ml_inference():
    fig, ax = plt.subplots(figsize=(13, 9))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.975, "SleepSense — ML Inference Service (Internal)",
            ha="center", va="top", fontsize=14, fontweight="bold",
            color=COLORS["header"])

    # Steps
    steps = [
        (COLORS["kafka"],   "Kafka Consumer",           "Receives: {chunk_id, s3_key, session_id}"),
        (COLORS["data"],    "S3 Download",               "Streaming audio fetch (no full-load into memory)"),
        (COLORS["service"], "Audio Preprocessing",
         "Decode Opus → PCM float32 (16kHz mono)\n"
         "Silence trim  |  Segment into 3s windows (50% overlap)\n"
         "Mel Spectrogram: n_mels=128, hop=512, n_fft=2048  |  Normalize [-1,1]"),
        (COLORS["ml"],      "CNN Classifier  (per window)",
         "Input: (1, 128, 128) Mel Spec\n"
         "Output: {snoring: 0.87, breathing: 0.10, silence: 0.02, ambient: 0.01}"),
        (COLORS["ml"],      "Intensity Regressor  (snore windows only)",
         "Input: MFCC deltas + spectrogram features\n"
         "Output: snore_intensity ∈ [0.0, 100.0]"),
        (COLORS["service"], "Window → Chunk Aggregation",
         "snore_ratio  |  avg_intensity  |  max_intensity\n"
         "events: [{start_sec, end_sec, class, intensity}, ...]"),
        (COLORS["data"],    "Persist Results",           "InfluxDB: snore_events  |  PostgreSQL: chunk analysis"),
        (COLORS["kafka"],   "Kafka Publish",             "analysis.complete  →  {session_id, chunk_id, summary}"),
    ]

    y = 0.905
    h = 0.085
    gap = 0.008
    for color, title, detail in steps:
        rounded_box(ax, 0.07, y - h, 0.86, h, color,
                    f"{title}\n{detail}", fontsize=8.5)
        if y - h > 0.05:
            arrow(ax, 0.5, y - h, 0.5, y - h - gap + 0.001)
        y -= h + gap

    # CNN architecture sidebar
    cnn = [
        "Conv2D(32, 3×3) → BN → MaxPool",
        "Conv2D(64, 3×3) → BN → MaxPool",
        "Conv2D(128, 3×3) → BN → MaxPool",
        "Conv2D(256, 3×3) → BN → GlobalAvgPool",
        "FC(512, ReLU) → Dropout(0.4)",
        "FC(4, Softmax)",
    ]
    bx = 0.74
    by_start = 0.58
    ax.text(bx + 0.12, by_start + 0.02, "CNN Architecture",
            ha="center", fontsize=8, fontweight="bold", color=COLORS["ml"])
    for i, layer in enumerate(cnn):
        by = by_start - i * 0.062
        rounded_box(ax, bx, by - 0.048, 0.23, 0.045, COLORS["ml"],
                    layer, fontsize=7)
        if i < len(cnn) - 1:
            arrow(ax, bx + 0.115, by - 0.048, bx + 0.115, by - 0.048 - 0.014)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "05_ML_Inference_Service.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 6 — Cloud Infrastructure
# ─────────────────────────────────────────────────────────────────────────────
def diagram_infrastructure():
    fig, ax = plt.subplots(figsize=(14, 12))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.985, "SleepSense — Cloud Infrastructure Architecture",
            ha="center", va="top", fontsize=15, fontweight="bold",
            color=COLORS["header"])

    # CDN
    rounded_box(ax, 0.35, 0.91, 0.30, 0.06, "#1A5276",
                "CloudFlare CDN\nDDoS  |  WAF  |  Cache", fontsize=9, bold=True)
    arrow(ax, 0.5, 0.91, 0.5, 0.875)

    # LB
    rounded_box(ax, 0.35, 0.825, 0.30, 0.055, "#1F618D",
                "Load Balancer\nAWS ALB / GCP LB", fontsize=9, bold=True)
    arrow(ax, 0.35, 0.855, 0.20, 0.79)
    arrow(ax, 0.65, 0.855, 0.80, 0.79)

    # API GW + WS GW
    rounded_box(ax, 0.04, 0.73, 0.28, 0.06, COLORS["gateway"],
                "API Gateway Cluster\n3+ replicas", fontsize=9)
    rounded_box(ax, 0.68, 0.73, 0.28, 0.06, COLORS["gateway"],
                "WebSocket Gateway\n2+ replicas", fontsize=9)
    arrow(ax, 0.18, 0.73, 0.40, 0.655)
    arrow(ax, 0.82, 0.73, 0.60, 0.655)

    # K8s cluster
    k8s_box = FancyBboxPatch((0.04, 0.385), 0.92, 0.265,
                              boxstyle="round,pad=0.01,rounding_size=0.02",
                              facecolor=COLORS["light_blue"],
                              edgecolor=COLORS["infra"], linewidth=2.5, zorder=2)
    ax.add_patch(k8s_box)
    ax.text(0.5, 0.645, "Kubernetes Cluster  (sleepsense-prod)",
            ha="center", fontsize=10, fontweight="bold",
            color=COLORS["infra"], zorder=3)

    svcs = [
        ("auth-svc\n2 replicas",       0.06,  0.52),
        ("user-svc\n2 replicas",       0.28,  0.52),
        ("audio-svc\n3 replicas",      0.50,  0.52),
        ("analytics-svc\n3 replicas",  0.72,  0.52),
        ("notif-svc\n2 replicas",      0.06,  0.40),
        ("insight-engine\n2 replicas", 0.28,  0.40),
    ]
    for label, bx, by in svcs:
        rounded_box(ax, bx, by, 0.18, 0.09, COLORS["service"],
                    label, fontsize=8.5)

    # ML inference (spanning)
    rounded_box(ax, 0.50, 0.395, 0.44, 0.10, COLORS["ml"],
                "ml-inference-svc\n2 GPU replicas (NVIDIA T4)\n"
                "Auto-scales 2 → 8 based on Kafka lag (KEDA)",
                fontsize=8.5, bold=True)

    # Managed services
    mgd_box = FancyBboxPatch((0.04, 0.12), 0.92, 0.245,
                              boxstyle="round,pad=0.01,rounding_size=0.02",
                              facecolor=COLORS["light_orange"],
                              edgecolor=COLORS["data"], linewidth=2.5, zorder=2)
    ax.add_patch(mgd_box)
    ax.text(0.5, 0.355, "Managed Services",
            ha="center", fontsize=10, fontweight="bold",
            color=COLORS["data"], zorder=3)

    mgd = [
        ("RDS PostgreSQL\nMulti-AZ\n1 primary + 2 replicas", COLORS["data"]),
        ("ElastiCache Redis\n3 shards\n(cluster mode)", COLORS["data"]),
        ("MSK Kafka\n3 brokers\n3 AZs", COLORS["kafka"]),
        ("InfluxDB Cloud\n(or K8s self-hosted)", "#E74C3C"),
        ("S3 + CloudFront\nAudio storage\n+ CDN delivery", COLORS["infra"]),
    ]
    for i, (label, color) in enumerate(mgd):
        bx = 0.06 + i * 0.185
        rounded_box(ax, bx, 0.14, 0.165, 0.19, color, label, fontsize=7.5)

    arrow(ax, 0.5, 0.385, 0.5, 0.365)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "06_Cloud_Infrastructure.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 7 — CI/CD Pipeline
# ─────────────────────────────────────────────────────────────────────────────
def diagram_cicd():
    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.98, "SleepSense — CI/CD Pipeline (GitHub Actions)",
            ha="center", va="top", fontsize=14, fontweight="bold",
            color=COLORS["header"])

    stages = [
        (COLORS["client"],  "Developer Push",
         "Feature branch  →  Pull Request created"),
        (COLORS["service"], "PR Checks (parallel)",
         "Lint (ruff, eslint)  |  Type check (mypy, tsc)\n"
         "Unit tests  |  Security scan (trivy, bandit)"),
        (COLORS["gateway"], "Code Review + Merge",
         "PR approved  →  Merged to main"),
        (COLORS["infra"],   "Build Pipeline",
         "Build Docker images  |  Integration tests (docker-compose)\n"
         "ML model validation (if model changed)  |  Push to ECR (git SHA tag)"),
        (COLORS["data"],    "Deploy to Staging",
         "Helm upgrade sleepsense-staging\n"
         "E2E tests (Playwright)  |  Load test (k6, 100 VUs)"),
        (COLORS["ml"],      "Deploy to Production",
         "Blue-Green deployment (zero downtime)\n"
         "Smoke tests  |  Monitor 10 min  |  Auto-rollback if error > 1%"),
    ]

    y = 0.885
    h = 0.105
    gap = 0.015
    for color, title, detail in stages:
        rounded_box(ax, 0.10, y - h, 0.80, h, color,
                    f"{title}\n{detail}", fontsize=9)
        if y - h > 0.05:
            arrow(ax, 0.5, y - h, 0.5, y - h - gap + 0.001)
        y -= h + gap

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "07_CICD_Pipeline.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 8 — Feature Engineering Pipeline
# ─────────────────────────────────────────────────────────────────────────────
def diagram_feature_engineering():
    fig, ax = plt.subplots(figsize=(13, 8))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.975, "SleepSense — Feature Engineering Pipeline",
            ha="center", va="top", fontsize=14, fontweight="bold",
            color=COLORS["header"])

    # Raw audio
    rounded_box(ax, 0.35, 0.865, 0.30, 0.075, COLORS["data"],
                "Raw Audio\nWAV / Opus  |  16kHz mono", fontsize=9, bold=True)
    arrow(ax, 0.5, 0.865, 0.5, 0.80)

    # Preprocessing
    rounded_box(ax, 0.10, 0.71, 0.80, 0.09, COLORS["service"],
                "Preprocessing Stage\n"
                "Resample → 16kHz  |  Stereo → Mono  |  Amplitude normalize  |  "
                "DC offset removal  |  Silence trim (-40 dBFS)",
                fontsize=8.5, bold=True)

    # Branches
    for x in [0.18, 0.50, 0.82]:
        arrow(ax, x, 0.71, x, 0.645)

    # Three feature families
    feats = [
        (0.04, "Spectral Features", COLORS["ml"],
         "Mel Spectrogram\n(128 mel, 3s window)\nLog-Mel Spec\n→ for CNN"),
        (0.36, "MFCC Features", COLORS["gateway"],
         "40 MFCCs\nDelta MFCCs\nDelta-Delta MFCCs\n→ for XGBoost"),
        (0.68, "Prosodic Features", COLORS["kafka"],
         "RMS Energy\nZero-Crossing Rate\nSpectral Centroid\nPitch (F0)  |  Formant F1"),
    ]
    for bx, name, color, detail in feats:
        rounded_box(ax, bx, 0.42, 0.28, 0.225, color,
                    f"{name}\n\n{detail}", fontsize=8.5)

    # Merge arrows
    for x in [0.18, 0.50, 0.82]:
        arrow(ax, x, 0.42, x, 0.375)

    rounded_box(ax, 0.30, 0.29, 0.40, 0.08, COLORS["infra"],
                "Feature Store (Feast)\nVersioned  |  Low-latency serving  |  Point-in-time correctness",
                fontsize=8.5, bold=True)

    # Down to models
    arrow(ax, 0.35, 0.29, 0.22, 0.23)
    arrow(ax, 0.65, 0.29, 0.78, 0.23)

    rounded_box(ax, 0.04, 0.14, 0.32, 0.09, COLORS["ml"],
                "CNN Classifier\n(Mel Spectrogram input)", fontsize=8.5)
    rounded_box(ax, 0.64, 0.14, 0.32, 0.09, "#C0392B",
                "XGBoost Regressor\n(MFCC + Prosodic input)", fontsize=8.5)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "08_Feature_Engineering_Pipeline.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 9 — Security Architecture
# ─────────────────────────────────────────────────────────────────────────────
def diagram_security():
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.975, "SleepSense — Security Architecture",
            ha="center", va="top", fontsize=14, fontweight="bold",
            color=COLORS["header"])

    flow = [
        (COLORS["client"],  "Client",          "iOS / Android / Web"),
        (COLORS["gateway"], "TLS 1.3",          "End-to-end encryption in transit"),
        (COLORS["gateway"], "API Gateway",      "SSL termination  |  CORS  |  Rate limiting"),
        (COLORS["ml"],      "JWT Validation",   "Access token (15 min TTL)\nRefresh token rotation (30d)"),
        (COLORS["service"], "RBAC",             "Roles: user  |  admin  |  researcher"),
        (COLORS["service"], "Microservice",     "Business logic (isolated service boundary)"),
    ]

    x = 0.06
    w = 0.125
    gap = 0.015
    y_center = 0.55
    h = 0.18
    for i, (color, label, detail) in enumerate(flow):
        bx = x + i * (w + gap)
        rounded_box(ax, bx, y_center - h/2, w, h, color,
                    f"{label}\n\n{detail}", fontsize=7.5)
        if i < len(flow) - 1:
            arrow(ax, bx + w, y_center, bx + w + gap, y_center)

    # Bottom security controls
    controls = [
        ("OAuth2\nGoogle / Apple\nSign-In", COLORS["client"]),
        ("AES-256\nAudio encrypted\nat rest (S3)", COLORS["data"]),
        ("PII\nAnonymization\nfor analytics", COLORS["service"]),
        ("HIPAA-Ready\nAudit logs\n+ encryption", COLORS["ml"]),
        ("On-Device\nTFLite option\n(no upload)", COLORS["infra"]),
    ]
    for i, (label, color) in enumerate(controls):
        bx = 0.06 + i * 0.185
        rounded_box(ax, bx, 0.12, 0.165, 0.22, color, label, fontsize=8.5)

    ax.text(0.5, 0.355, "Additional Security Controls",
            ha="center", fontsize=10, fontweight="bold", color=COLORS["header"])

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "09_Security_Architecture.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# DIAGRAM 10 — Database Schema Overview
# ─────────────────────────────────────────────────────────────────────────────
def diagram_database():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor(COLORS["bg"])

    ax.text(0.5, 0.985, "SleepSense — Polyglot Database Architecture",
            ha="center", va="top", fontsize=15, fontweight="bold",
            color=COLORS["header"])

    # PostgreSQL
    section_label(ax, 0.02, 0.50, 0.46, 0.45, "PostgreSQL  (Relational)", COLORS["data"])
    pg_tables = [
        ("users", "id, email, password_hash,\ncreated_at, oauth_provider"),
        ("sleep_sessions", "id, user_id, start_time,\nend_time, quality_score"),
        ("audio_chunks", "id, session_id, s3_key,\nchunk_index, analysis_result"),
        ("insights", "id, session_id, rule_name,\nrecommendation, created_at"),
        ("lifestyle_logs", "id, user_id, date, alcohol,\nsleep_position, notes"),
    ]
    for i, (tbl, cols) in enumerate(pg_tables):
        row = i // 2
        col = i % 2
        bx = 0.04 + col * 0.23
        by = 0.835 - row * 0.155
        rounded_box(ax, bx, by, 0.21, 0.125, COLORS["data"],
                    f"{tbl}\n{cols}", fontsize=7.5)

    # InfluxDB
    section_label(ax, 0.52, 0.68, 0.46, 0.27, "InfluxDB  (Time-Series)", "#E74C3C")
    rounded_box(ax, 0.54, 0.76, 0.42, 0.155, "#E74C3C",
                "Measurement: snore_events\n"
                "Tags: session_id, user_id, chunk_id\n"
                "Fields: class, intensity, confidence\n"
                "Timestamp: nanosecond precision", fontsize=8.5)
    rounded_box(ax, 0.54, 0.695, 0.42, 0.055, "#C0392B",
                "Measurement: session_metrics  (5-min aggregations)\n"
                "Fields: snore_ratio, avg_intensity, event_count",
                fontsize=7.5)

    # Redis
    section_label(ax, 0.52, 0.38, 0.46, 0.27, "Redis  (Cache)", "#F39C12")
    redis_keys = [
        ("jwt:refresh:{user_id}", "Refresh token  |  TTL 30d"),
        ("rate:{ip}:{endpoint}", "Request count  |  TTL 60s"),
        ("session:status:{id}", "Processing state  |  TTL 2h"),
        ("inference:cache:{hash}", "ML result cache  |  TTL 7d"),
    ]
    for i, (key, val) in enumerate(redis_keys):
        by = 0.60 - i * 0.055
        rounded_box(ax, 0.54, by, 0.42, 0.045, "#F39C12",
                    f"{key}  →  {val}", fontsize=7.5)

    # S3
    section_label(ax, 0.52, 0.06, 0.46, 0.28, "S3 / MinIO  (Object Storage)", COLORS["infra"])
    rounded_box(ax, 0.54, 0.14, 0.42, 0.09, COLORS["infra"],
                "Audio: {bucket}/{user_id}/{session_id}/chunk_N.opus\n"
                "Spectrogram cache: {bucket}/spectrograms/{chunk_id}.npy\n"
                "ML Models: s3://sleepsense-ml/models/{version}/",
                fontsize=7.5)
    rounded_box(ax, 0.54, 0.075, 0.42, 0.055,  "#148F77",
                "Lifecycle: audio → S3 Glacier after 90d  |  Delete after 12 months (default)",
                fontsize=7.5)

    # PostgreSQL section lower
    section_label(ax, 0.02, 0.06, 0.46, 0.41, "", "#AAAAAA")
    pg2_tables = [
        ("goals", "id, user_id, target_score,\ndeadline, achieved_at"),
        ("notifications", "id, user_id, type,\nchannel, sent_at"),
        ("user_devices", "id, user_id, fcm_token,\nplatform, last_seen"),
    ]
    for i, (tbl, cols) in enumerate(pg2_tables):
        bx = 0.04 + (i % 2) * 0.23
        by = 0.38 - (i // 2) * 0.155
        rounded_box(ax, bx, by, 0.21, 0.125, COLORS["data"],
                    f"{tbl}\n{cols}", fontsize=7.5)

    plt.tight_layout()
    out = os.path.join(OUT_DIR, "10_Database_Architecture.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=COLORS["bg"])
    plt.close()
    print(f"  Saved: {out}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "figure.dpi": 100,
    })
    print("Generating SleepSense architecture diagrams...\n")
    diagram_hla()
    diagram_data_flow()
    diagram_microservice_layers()
    diagram_ml_pipeline()
    diagram_ml_inference()
    diagram_infrastructure()
    diagram_cicd()
    diagram_feature_engineering()
    diagram_security()
    diagram_database()
    print("\nAll diagrams generated successfully!")
