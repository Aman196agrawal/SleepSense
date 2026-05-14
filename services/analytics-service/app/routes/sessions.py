import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import SleepSession, TimelineBucket, SessionInsight
from app.security import get_current_user_id
from app.seed import seed_user, _grade, _compute_score, _make_timeline, INSIGHT_TEMPLATES
from app.influx_client import get_influx_write_api
from app.kafka_client import emit
from app.routes.ws import manager as ws_manager
import random

router = APIRouter()

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
            pass  # best-effort — never block the response

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


@router.post("/{session_id}/end")
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

        for b in _make_timeline(session_id, max(duration, 30), snore_ratio, rng):
            db.add(b)

    score = _compute_score(snore_ratio, avg_int, interruptions, duration)

    session.ended_at              = now
    session.duration_minutes      = duration
    session.status                = "complete"
    session.sleep_quality_score   = score
    session.sleep_quality_grade   = _grade(score)
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

    return _session_dict(session)


@router.get("")
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
    return [_session_dict(s) for s in sessions]


@router.get("/{session_id}")
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
    return _session_dict(session)


def _session_dict(s: SleepSession) -> dict:
    return {
        "id": s.id,
        "started_at":           s.started_at.isoformat() if s.started_at else None,
        "ended_at":             s.ended_at.isoformat()   if s.ended_at   else None,
        "duration_minutes":     s.duration_minutes,
        "status":               s.status,
        "sleep_quality_score":  s.sleep_quality_score,
        "sleep_quality_grade":  s.sleep_quality_grade,
        "snoring_duration_min": s.snoring_duration_min,
        "snoring_percentage":   s.snoring_percentage,
        "snore_events_per_hour":s.snore_events_per_hour,
        "avg_snore_intensity":  s.avg_snore_intensity,
        "max_snore_intensity":  s.max_snore_intensity,
        "peak_snoring_hour":    s.peak_snoring_hour,
        "total_chunks":         s.total_chunks,
        "processed_chunks":     s.processed_chunks,
    }
