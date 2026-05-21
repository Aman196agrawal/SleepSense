import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.database import get_db
from app.influx_client import get_influx_write_api
from app.kafka_client import emit
from app.models import SleepSession, TimelineBucket, SessionInsight
from app.routes.ws import manager as ws_manager
from app.scoring import INSIGHT_TEMPLATES, compute_score, grade, make_timeline
from app.security import get_current_user_id
from app.seed import seed_user

router = APIRouter()
_logger = logging.getLogger(__name__)


class SessionResponse(BaseModel):
    id: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: str
    sleep_quality_score: Optional[float] = None
    sleep_quality_grade: Optional[str] = None
    snoring_duration_min: Optional[int] = None
    snoring_percentage: Optional[float] = None
    snore_events_per_hour: Optional[float] = None
    avg_snore_intensity: Optional[float] = None
    max_snore_intensity: Optional[float] = None
    peak_snoring_hour: Optional[int] = None
    total_chunks: Optional[int] = None
    processed_chunks: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

def _ensure_seeded(user_id: str, db: Session):
    seed_user(user_id, db)


# ── Chunk upload ───────────────────────────────────────────────────────────────

class ChunkData(BaseModel):
    chunk_index: int
    avg_intensity: float
    dominant_class: str
    snore_event_count: int

@router.post("/{session_id}/chunks", status_code=201)
def upload_chunk(
    session_id: str,
    chunk: ChunkData,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id, SleepSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    bucket = TimelineBucket(
        id=str(uuid.uuid4()),
        session_id=session_id,
        bucket_index=chunk.chunk_index,
        offset_minutes=chunk.chunk_index // 2,   # each chunk ≈ 30s = 0.5 min
        avg_intensity=round(chunk.avg_intensity, 1),
        dominant_class=chunk.dominant_class,
        snore_event_count=chunk.snore_event_count,
    )
    db.add(bucket)
    session.total_chunks     = max(session.total_chunks or 0, chunk.chunk_index + 1)
    session.processed_chunks = session.total_chunks
    db.commit()

    # ── InfluxDB: write snore event time-series point ─────────────────────────
    write_api = get_influx_write_api()
    if write_api:
        try:
            from influxdb_client import Point
            from app.config import settings as _s
            point = (
                Point("snore_events")
                .tag("session_id", session_id)
                .tag("user_id", user_id)
                .tag("dominant_class", chunk.dominant_class)
                .field("avg_intensity",     float(chunk.avg_intensity))
                .field("snore_event_count", int(chunk.snore_event_count))
                .field("chunk_index",       int(chunk.chunk_index))
            )
            write_api.write(bucket=_s.INFLUXDB_BUCKET, org=_s.INFLUXDB_ORG, record=point)
        except Exception:
            # best-effort — never block the response, but leave a breadcrumb
            _logger.warning(
                "influxdb write failed for session=%s chunk=%s",
                session_id, chunk.chunk_index, exc_info=True,
            )

    # ── Kafka: emit audio.chunk.uploaded for ML inference pipeline ────────────
    emit("audio.chunk.uploaded", {
        "session_id":       session_id,
        "user_id":          user_id,
        "chunk_index":      chunk.chunk_index,
        "avg_intensity":    chunk.avg_intensity,
        "dominant_class":   chunk.dominant_class,
        "snore_event_count":chunk.snore_event_count,
    })

    # ── WebSocket: notify connected clients about the processed chunk ─────────
    background_tasks.add_task(ws_manager.send_to_user, user_id, {
        "event":          "chunk.analyzed",
        "session_id":     session_id,
        "chunk_index":    chunk.chunk_index,
        "dominant_class": chunk.dominant_class,
        "avg_intensity":  round(chunk.avg_intensity, 1),
    })

    return {"status": "ok", "chunk_index": chunk.chunk_index}


# ── Session lifecycle ──────────────────────────────────────────────────────────

@router.post("", status_code=201)
def start_session(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    _ensure_seeded(user_id, db)
    session = SleepSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        status="recording",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "status": session.status, "started_at": session.started_at}


@router.post("/{session_id}/end", response_model=SessionResponse)
def end_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id, SleepSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    duration = max(1, int((now - session.started_at).total_seconds() / 60))

    # ── Use real chunk data if it was uploaded ────────────────────────────────
    buckets = (
        db.query(TimelineBucket)
        .filter(TimelineBucket.session_id == session_id)
        .order_by(TimelineBucket.bucket_index)
        .all()
    )

    if buckets:
        snoring_buckets = [b for b in buckets if b.dominant_class == "snoring"]
        snore_ratio     = len(snoring_buckets) / len(buckets)
        avg_int         = (
            sum(b.avg_intensity for b in snoring_buckets) / len(snoring_buckets)
            if snoring_buckets else 0.0
        )
        max_int         = max((b.avg_intensity for b in buckets), default=0.0)
        interruptions   = sum(b.snore_event_count for b in buckets)

        # Peak snoring hour: find the hour-block with highest combined intensity
        hour_intensity: dict = {}
        for b in buckets:
            hr = (session.started_at.hour + b.offset_minutes // 60) % 24
            hour_intensity[hr] = hour_intensity.get(hr, 0) + b.avg_intensity
        peak_hour = max(hour_intensity, key=hour_intensity.get) if hour_intensity else 0
    else:
        # ── Fallback: no chunks uploaded — use deterministic simulation ───────
        rng           = random.Random(session_id)
        snore_ratio   = rng.uniform(0.10, 0.35)
        avg_int       = rng.uniform(30, 70)
        max_int       = min(avg_int * rng.uniform(1.2, 1.7), 100)
        interruptions = rng.randint(2, 10)
        peak_hour     = rng.randint(0, 3)

        for b in make_timeline(session_id, max(duration, 30), snore_ratio, rng):
            db.add(b)

    score = compute_score(snore_ratio, avg_int, interruptions, duration)

    session.ended_at              = now
    session.duration_minutes      = duration
    session.status                = "complete"
    session.sleep_quality_score   = score
    session.sleep_quality_grade   = grade(score)
    session.snoring_duration_min  = int(duration * snore_ratio)
    session.snoring_percentage    = round(snore_ratio * 100, 1)
    session.snore_events_per_hour = round(interruptions / max(duration / 60, 0.1), 1)
    session.avg_snore_intensity   = round(avg_int, 1)
    session.max_snore_intensity   = round(max_int, 1)
    session.peak_snoring_hour     = peak_hour
    session.total_chunks          = session.total_chunks or max(1, duration // 30)
    session.processed_chunks      = session.total_chunks

    # Generate one insight based on the computed score
    rng2 = random.Random(session_id + "insight")
    tmpl = rng2.choice(INSIGHT_TEMPLATES)
    db.add(SessionInsight(
        id=str(uuid.uuid4()),
        session_id=session_id,
        user_id=user_id,
        insight_type=tmpl[0],
        priority=5,
        title=tmpl[1],
        body=tmpl[2],
    ))

    db.commit()
    db.refresh(session)

    # ── Kafka: emit session.ended for downstream consumers ─────────────────────
    emit("session.ended", {
        "session_id":          session_id,
        "user_id":             user_id,
        "status":              "complete",
        "sleep_quality_score": session.sleep_quality_score,
        "snoring_percentage":  session.snoring_percentage,
        "duration_minutes":    session.duration_minutes,
    })

    # ── WebSocket: notify connected clients that session is complete ───────────
    background_tasks.add_task(ws_manager.send_to_user, user_id, {
        "event":               "session.complete",
        "session_id":          session_id,
        "sleep_quality_score": session.sleep_quality_score,
        "sleep_quality_grade": session.sleep_quality_grade,
        "snoring_percentage":  session.snoring_percentage,
        "duration_minutes":    session.duration_minutes,
    })

    return session


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    limit: int = 20,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    _ensure_seeded(user_id, db)
    sessions = (
        db.query(SleepSession)
        .filter(SleepSession.user_id == user_id, SleepSession.status == "complete")
        .order_by(SleepSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return sessions


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id, SleepSession.user_id == user_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
