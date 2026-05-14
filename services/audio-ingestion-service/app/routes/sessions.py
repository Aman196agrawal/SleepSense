import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.kafka_client import emit
from app.models import AudioChunk, SleepSession
from app.redis_client import get_session_status, set_session_status
from app.s3_client import upload_chunk as s3_upload
from app.security import create_upload_token, get_current_user_id
from app.config import settings

router = APIRouter()

ALLOWED_MIME_TYPES = {"audio/opus", "audio/wav", "audio/m4a", "audio/x-m4a", "audio/mpeg", "audio/webm"}
MAX_CHUNK_BYTES = settings.MAX_CHUNK_SIZE_MB * 1024 * 1024

# In-memory fallback for chunk rate limiting when Redis is unavailable
_chunk_rl: dict[str, list[float]] = {}


def _check_chunk_rate_limit(user_id: str) -> None:
    from app.redis_client import get_redis
    r = get_redis()
    if r:
        key = f"ratelimit:chunk:{user_id}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, 3600)
        if count > settings.CHUNK_RATE_LIMIT_PER_HOUR:
            raise HTTPException(status_code=429, detail="Chunk upload rate limit exceeded. Max 120 per hour.")
    else:
        now = time.time()
        ts = [t for t in _chunk_rl.get(user_id, []) if now - t < 3600]
        ts.append(now)
        _chunk_rl[user_id] = ts
        if len(ts) > settings.CHUNK_RATE_LIMIT_PER_HOUR:
            raise HTTPException(status_code=429, detail="Chunk upload rate limit exceeded. Max 120 per hour.")


# ── POST /sessions ─────────────────────────────────────────────────────────────

@router.post("", status_code=201)
def start_session(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    existing = db.query(SleepSession).filter(
        SleepSession.user_id == user_id,
        SleepSession.status == "recording",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="An active recording session already exists")

    session = SleepSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        status="recording",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return {
        "session_id":    session.id,
        "upload_token":  create_upload_token(session.id),
        "status":        session.status,
        "started_at":    session.started_at.isoformat(),
    }


# ── POST /sessions/{session_id}/chunks ─────────────────────────────────────────

@router.post("/{session_id}/chunks", status_code=202)
async def upload_chunk(
    session_id: str,
    chunk_index: int      = Form(...),
    duration_seconds: int = Form(...),
    audio: UploadFile     = File(...),
    user_id: str          = Depends(get_current_user_id),
    db: Session           = Depends(get_db),
):
    _check_chunk_rate_limit(user_id)

    # MIME type guard
    content_type = audio.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format '{content_type}'. Accepted: opus, wav, m4a, mpeg, webm.",
        )

    # Session ownership + active-status check
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id,
        SleepSession.user_id == user_id,
        SleepSession.status == "recording",
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or not in recording state")

    # Sequential index enforcement
    existing_count = db.query(AudioChunk).filter(AudioChunk.session_id == session_id).count()
    if chunk_index != existing_count:
        raise HTTPException(
            status_code=422,
            detail=f"chunk_index must be sequential; expected {existing_count}, got {chunk_index}",
        )

    # Read body and enforce size limit
    audio_bytes = await audio.read()
    file_size = len(audio_bytes)
    if file_size > MAX_CHUNK_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio chunk exceeds maximum size of {settings.MAX_CHUNK_SIZE_MB} MB",
        )

    # S3 upload (best-effort — never blocks the response)
    s3_key = f"{user_id}/{session_id}/chunk_{chunk_index:03d}.opus"
    s3_upload(BytesIO(audio_bytes), s3_key, content_type)

    # Persist chunk record
    chunk_id = str(uuid.uuid4())
    chunk = AudioChunk(
        id=chunk_id,
        session_id=session_id,
        chunk_index=chunk_index,
        s3_key=s3_key,
        duration_seconds=duration_seconds,
        file_size_bytes=file_size,
        content_type=content_type,
        status="pending",
    )
    db.add(chunk)
    session.total_chunks = chunk_index + 1
    db.commit()

    # Kafka: trigger ML inference pipeline
    emit("audio.chunk.uploaded", {
        "chunk_id":        chunk_id,
        "session_id":      session_id,
        "user_id":         user_id,
        "s3_key":          s3_key,
        "chunk_index":     chunk_index,
        "duration_seconds":duration_seconds,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    })

    return {"chunk_id": chunk_id, "chunk_index": chunk_index, "status": "queued"}


# ── POST /sessions/{session_id}/end ────────────────────────────────────────────

class EndSessionRequest(BaseModel):
    ended_at:         Optional[datetime] = None
    notes:            Optional[str]      = None
    room_temperature: Optional[float]    = None


@router.post("/{session_id}/end")
def end_session(
    session_id: str,
    body: EndSessionRequest,
    user_id: str    = Depends(get_current_user_id),
    db: Session     = Depends(get_db),
):
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id,
        SleepSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "recording":
        raise HTTPException(status_code=409, detail="Session is not in recording state")

    ended_at = (body.ended_at.replace(tzinfo=None) if body.ended_at else
                datetime.now(timezone.utc).replace(tzinfo=None))

    session.ended_at         = ended_at
    session.status           = "processing"
    session.notes            = body.notes
    session.room_temperature = body.room_temperature
    db.commit()

    total = session.total_chunks or 0

    # Cache initial processing state in Redis
    set_session_status(session_id, {
        "status":           "processing",
        "processed_chunks": 0,
        "total_chunks":     total,
        "percent_complete": 0.0,
    })

    # Kafka: notify Analytics + ML downstream
    emit("session.ended", {
        "session_id":  session_id,
        "user_id":     user_id,
        "total_chunks":total,
        "ended_at":    ended_at.isoformat(),
    })

    return {
        "session_id":               session_id,
        "status":                   "processing",
        "estimated_ready_in_seconds": 120,
    }


# ── GET /sessions/{session_id}/status ──────────────────────────────────────────

@router.get("/{session_id}/status")
def get_status(
    session_id: str,
    user_id: str    = Depends(get_current_user_id),
    db: Session     = Depends(get_db),
):
    # Redis cache hit
    cached = get_session_status(session_id)
    if cached:
        return cached

    session = db.query(SleepSession).filter(
        SleepSession.id == session_id,
        SleepSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    total     = session.total_chunks or 0
    processed = db.query(AudioChunk).filter(
        AudioChunk.session_id == session_id,
        AudioChunk.status == "done",
    ).count()
    percent = round(processed / total * 100, 1) if total > 0 else 0.0

    result = {
        "status":           session.status,
        "processed_chunks": processed,
        "total_chunks":     total,
        "percent_complete": percent,
    }
    set_session_status(session_id, result)
    return result
