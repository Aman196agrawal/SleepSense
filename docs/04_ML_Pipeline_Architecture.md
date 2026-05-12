# ML Pipeline Architecture
## SleepSense — AI/ML System Design

---

## 1. ML System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ML SYSTEM ARCHITECTURE                        │
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │  Data        │    │  Training    │    │  Serving / Inference  │  │
│  │  Pipeline    │───►│  Pipeline    │───►│  Pipeline             │  │
│  └──────────────┘    └──────────────┘    └───────────────────────┘  │
│         │                   │                        │               │
│         ▼                   ▼                        ▼               │
│  ┌──────────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │  Feature     │    │  Experiment  │    │  Model Registry       │  │
│  │  Store       │    │  Tracking    │    │  (MLflow)             │  │
│  │  (Feast)     │    │  (MLflow)    │    │                       │  │
│  └──────────────┘    └──────────────┘    └───────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                  MLOps / Monitoring                             │ │
│  │  Data Drift Detection │ Model Performance Monitoring │ Retraining│ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Model Catalog

### Model 1: Snore Classifier (Primary)
| Attribute         | Detail                                              |
|-------------------|-----------------------------------------------------|
| Task              | Multi-class classification                          |
| Input             | Mel spectrogram (128×128, 3s window)                |
| Output            | 4-class probabilities: snoring/breathing/silence/ambient |
| Architecture      | EfficientNet-B0 (transfer learning from AudioSet)   |
| Training data     | ESC-50 + custom snoring dataset (~50k samples)      |
| Accuracy target   | >92% on held-out test set                           |
| Latency target    | <50ms per window on CPU                             |
| Model size        | ~20MB (full), ~5MB (TFLite quantized)               |

### Model 2: Snore Intensity Regressor
| Attribute         | Detail                                              |
|-------------------|-----------------------------------------------------|
| Task              | Regression                                          |
| Input             | MFCC features (40 coefficients) + RMS energy        |
| Output            | Intensity score 0–100                               |
| Architecture      | Gradient Boosted Trees (XGBoost)                    |
| Training target   | Correlated with dB SPL measurements                 |
| MAE target        | <5 intensity points                                 |

### Model 3: Sleep Stage Estimator (Phase 2)
| Attribute         | Detail                                              |
|-------------------|-----------------------------------------------------|
| Task              | Time-series classification                          |
| Input             | 30s audio + (optional) accelerometer from phone     |
| Output            | Sleep stage: Awake/Light/Deep/REM                   |
| Architecture      | Bidirectional LSTM + Attention                      |
| Note              | Lower accuracy without wearable; clearly disclosed  |

### Model 4: Apnea Risk Screener (Phase 2)
| Attribute         | Detail                                              |
|-------------------|-----------------------------------------------------|
| Task              | Binary classification                               |
| Input             | 7-night session history features                    |
| Output            | Low/Medium/High risk score + confidence             |
| Note              | NOT a medical diagnosis; shows "consult a doctor"   |
| Regulatory note   | May require FDA/CE review before commercial use     |

---

## 3. Feature Engineering Pipeline

```
Raw Audio (WAV/Opus, 16kHz mono)
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                    PREPROCESSING STAGE                         │
│                                                                │
│  1. Resample to 16kHz (if needed)                             │
│  2. Convert stereo → mono                                      │
│  3. Normalize amplitude (peak normalization)                   │
│  4. Remove DC offset                                           │
│  5. Trim silence (threshold: -40 dBFS)                        │
└────────────────────────────┬──────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│  SPECTRAL    │    │    MFCC      │    │   PROSODIC       │
│  FEATURES    │    │  FEATURES    │    │   FEATURES       │
│              │    │              │    │                  │
│ Mel Spec     │    │ 40 MFCCs     │    │ RMS Energy       │
│ (128 mel,    │    │ Delta MFCCs  │    │ Zero-Cross Rate  │
│  3s window)  │    │ Delta-Delta  │    │ Spectral Centroid│
│              │    │ MFCCs        │    │ Spectral Rolloff │
│ Log-Mel Spec │    │              │    │ Pitch (F0)       │
│ (for CNN)    │    │ (for XGBoost)│    │ Formant F1       │
└──────────────┘    └──────────────┘    └──────────────────┘
        │                    │                    │
        └────────────────────┴────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  Feature Store  │
                    │   (Feast)       │
                    └─────────────────┘
```

---

## 4. Training Pipeline (Apache Airflow DAG)

```
DAG: snore_model_training (weekly / triggered)

Task 1: data_validation
  ├── Check dataset schema
  ├── Compute class distribution
  ├── Flag label imbalances (>5:1 ratio triggers SMOTE)
  └── Output: validated_dataset artifact

Task 2: feature_engineering
  ├── Compute mel spectrograms for all samples
  ├── Compute MFCC features
  ├── Apply augmentation (time stretch, pitch shift, noise injection)
  └── Output: feature_dataset artifact

Task 3: train_classifier
  ├── Load EfficientNet-B0 pretrained weights (AudioSet)
  ├── Freeze backbone, train head (5 epochs)
  ├── Unfreeze all, fine-tune (20 epochs)
  ├── Learning rate: 1e-4 → cosine decay
  ├── Loss: CrossEntropyLoss with class weights
  └── Log metrics to MLflow

Task 4: evaluate_classifier
  ├── Compute: Accuracy, Precision, Recall, F1 (macro)
  ├── Confusion matrix
  ├── Per-class ROC-AUC
  └── FAIL pipeline if F1 < 0.90

Task 5: train_intensity_regressor
  ├── Feature matrix: [MFCC stats, spectral features, energy]
  ├── XGBoost regressor with hyperparameter tuning (Optuna)
  └── Log MAE, R² to MLflow

Task 6: model_registration
  ├── Compare vs. current production model
  ├── IF improvement > 1% F1 → register as "candidate"
  └── Set status "staging" (awaiting A/B test approval)

Task 7: export_tflite
  ├── Quantize model (INT8 post-training quantization)
  ├── Validate accuracy within 2% of full-precision model
  └── Upload to S3: s3://sleepsense-ml/models/tflite/
```

---

## 5. Training Data Strategy

### Datasets
| Dataset              | Samples | Classes                                        | Source                  |
|----------------------|---------|------------------------------------------------|-------------------------|
| ESC-50               | 2,000   | Environmental sounds (breathing, snoring subset)| Public / Kaggle         |
| Snoring Dataset      | 10,000  | Snoring vs. non-snoring                        | Kaggle                  |
| Custom collected     | ~5,000  | In-app consented recordings                    | User opt-in (Phase 2)   |
| Synthetic augmented  | ~50,000 | All classes (augmented from above)             | Generated in pipeline   |

### Data Augmentation Techniques
```python
augmentations = [
    TimeStretch(rate_range=(0.8, 1.2)),         # vary speaking rate
    PitchShift(semitones_range=(-2, 2)),         # vary pitch
    AddGaussianNoise(std_range=(0.001, 0.015)),  # room noise simulation
    RoomSimulation(rt60_range=(0.1, 0.8)),       # reverb variation
    VolumeControl(gain_range=(-6, +6)),          # dB variation
    TimeShift(shift_range=(-0.2, 0.2)),          # temporal shift
]
```

---

## 6. Model Serving Architecture

```
┌─────────────────────────────────────────────────────┐
│                 ML INFERENCE SERVICE                  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │              Model Manager                     │  │
│  │  - Load models from S3 on startup              │  │
│  │  - Hot-reload on new model registration        │  │
│  │  - A/B test traffic splitting                  │  │
│  └─────────────────────┬──────────────────────────┘  │
│                        │                             │
│          ┌─────────────┴──────────────┐              │
│          ▼                            ▼              │
│  ┌──────────────┐          ┌──────────────────────┐  │
│  │ Classifier   │          │  Intensity Regressor │  │
│  │  (PyTorch)   │          │    (XGBoost/ONNX)    │  │
│  │  GPU Worker  │          │    CPU Worker        │  │
│  │  (2 replicas)│          │    (4 replicas)      │  │
│  └──────────────┘          └──────────────────────┘  │
│                                                      │
│  ┌────────────────────────────────────────────────┐  │
│  │           Inference Cache (Redis)              │  │
│  │  Key: hash(audio_features) → cached result    │  │
│  │  TTL: 7 days (same audio chunk → same result) │  │
│  └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 7. Model Monitoring & Drift Detection

### Metrics Tracked (Evidently AI)
```
Data Drift Metrics:
  - Feature distribution shift (KS test, p-value < 0.05 → alert)
  - Audio characteristics drift (avg energy, spectral centroid)

Model Performance Metrics:
  - Weekly: spot-check 1% of predictions against user feedback labels
  - Precision@snoring on feedback-corrected labels
  - False positive rate (users marking "not snoring")

Business Metrics:
  - Average session quality score trend
  - User correction rate (users who override ML results)
  - App rating correlation with model accuracy

Alerts (PagerDuty):
  - Model accuracy drops > 5% week-over-week
  - Inference latency > 5s P95
  - Kafka consumer lag > 1000 messages
```

---

## 8. On-Device Inference (TFLite)

### When to Use
- No internet connection detected
- User enables "Private Mode" (no audio leaves device)
- Latency-sensitive real-time feedback during recording

### Model Optimization
```
Full PyTorch Model (20MB, float32)
    │
    ▼ Export to ONNX
ONNX Model (18MB)
    │
    ▼ Convert to TFLite
TFLite Model (float16) (10MB)
    │
    ▼ Post-training quantization (INT8)
TFLite Quantized (5MB) ← deployed to mobile
    │
    Accuracy: ≥90% of full-precision model
    Latency: <100ms per 3s window on mid-range phone (ARM Cortex-A55)
```

---

## 9. Ethical AI Considerations

| Concern              | Mitigation                                                           |
|----------------------|----------------------------------------------------------------------|
| Medical claims       | Clearly label as "wellness tool, not medical device"                 |
| False apnea alarms   | Confidence threshold > 0.85 required before showing risk alert       |
| Bias in training data| Stratify dataset by age, gender, ethnicity; report per-group metrics |
| Privacy              | Audio never used for training without explicit opt-in consent        |
| Model explainability | Show spectrogram heatmaps (Grad-CAM) on classification decisions     |
| Data minimization    | On-device option; raw audio auto-deleted after 12 months             |
