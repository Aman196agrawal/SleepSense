"""
Full ML inference pipeline for a single audio chunk.
Called by the Kafka consumer for each audio.chunk.uploaded event.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

import numpy as np

from app.aggregator import aggregate
from app.classifier import SnoreClassifier
from app.features import extract_features
from app.preprocessing import preprocess_chunk
from app.regressor import IntensityRegressor

_logger = logging.getLogger(__name__)

HOP_SECS    = 1.5
WINDOW_SECS = 3.0


def process_chunk(
    *,
    chunk_id:        str,
    session_id:      str,
    user_id:         str,
    audio_bytes:     bytes,
    chunk_index:     int,
    duration_seconds:int,
    classifier:      SnoreClassifier,
    regressor:       IntensityRegressor,
    db,
    influx_write,
    kafka_emit:      Callable,
) -> dict:
    """
    Run the full inference pipeline for one 30-second audio chunk.

    Pipeline
    --------
    1. Preprocess  → mel spectrograms + raw PCM windows
    2. Classify    → per-window {class, confidence}
    3. Regress     → per-window intensity (snoring windows only)
    4. Aggregate   → chunk-level summary
    5. Write       → InfluxDB (snore_events) + PostgreSQL (audio_chunks)
    6. Emit        → analysis.complete Kafka event

    Returns
    -------
    Chunk-level summary dict.
    """
    # 1. Preprocess
    spectrograms, audio_windows = preprocess_chunk(audio_bytes)
    n_windows = len(spectrograms)
    _logger.debug("chunk %s: %d windows", chunk_id, n_windows)

    # 2. Classify all windows (batch call to CNN)
    classifications = classifier.predict(spectrograms)

    # 3. Build per-window result; regress intensity for snoring windows
    window_results = []
    for i, (cls, win) in enumerate(zip(classifications, audio_windows)):
        intensity = 0.0
        if cls["dominant_class"] == "snoring":
            feats     = extract_features(win)
            intensity = regressor.predict(feats)
        window_results.append({
            "start_sec":  round(i * HOP_SECS, 1),
            "end_sec":    round(i * HOP_SECS + WINDOW_SECS, 1),
            "class":      cls["dominant_class"],
            "confidence": cls["confidence"],
            "intensity":  intensity,
        })

    # 4. Aggregate
    summary = aggregate(window_results)

    # 5a. Write to InfluxDB
    _write_influx(influx_write, session_id, user_id, chunk_index, window_results)

    # 5b. Update audio_chunks row in PostgreSQL
    _update_db(db, chunk_id, summary)

    # 6. Emit analysis.complete
    kafka_emit("analysis.complete", {
        "chunk_id":    chunk_id,
        "session_id":  session_id,
        "user_id":     user_id,
        "chunk_index": chunk_index,
        "summary":     summary,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    })

    return summary


# ── Internal helpers ──────────────────────────────────────────────────────────

def _write_influx(write_api, session_id: str, user_id: str, chunk_index: int, results: list):
    if write_api is None:
        return
    try:
        from influxdb_client import Point
        from app.config import settings
        for r in results:
            point = (
                Point("snore_events")
                .tag("session_id",  session_id)
                .tag("user_id",     user_id)
                .tag("event_class", r["class"])
                .field("intensity",    float(r["intensity"]))
                .field("confidence",   float(r["confidence"]))
                .field("chunk_index",  int(chunk_index))
                .field("start_sec",    float(r["start_sec"]))
            )
            write_api.write(bucket=settings.INFLUXDB_BUCKET, org=settings.INFLUXDB_ORG, record=point)
    except Exception as exc:
        _logger.warning("InfluxDB write failed: %s", exc)


def _update_db(db, chunk_id: str, summary: dict):
    if db is None:
        return
    try:
        from app.models import AudioChunk
        chunk = db.query(AudioChunk).filter(AudioChunk.id == chunk_id).first()
        if chunk:
            chunk.status          = "done"
            chunk.analysis_result = json.dumps(summary)
            chunk.processed_at    = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
    except Exception as exc:
        _logger.warning("DB update failed for chunk %s: %s", chunk_id, exc)
