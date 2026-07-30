import logging
import re
import time
import uuid
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

_logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I
)

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.kafka_client import emit
from app.models import AudioChunk, SleepSession
from app.redis_client import get_session_status, set_session_status
from app.s3_client import upload_chunk as s3_upload, delete_session_audio as s3_delete_session
from app.security import create_upload_token, get_current_user_id, verify_upload_token
from app.config import settings

router = APIRouter()

ALLOWED_MIME_TYPES = {"audio/opus", "audio/wav", "audio/m4a", "audio/x-m4a", "audio/mpeg", "audio/webm"}
MAX_CHUNK_BYTES = settings.MAX_CHUNK_SIZE_MB * 1024 * 1024


def _sniff_format(data: bytes) -> str | None:
    """Identify the audio container from its magic bytes, returning a file
    extension, or None if it is not recognised audio.

    Deliberately reads the bytes rather than the client-supplied Content-Type,
    which is trivially spoofable. The extension is used for the storage key, so
    getting it from the actual content is what keeps the key honest.
    """
    if len(data) < 12:
        return None
    if data[:4] == b"OggS":                                   # Ogg (Opus/Vorbis)
        return "opus"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":         # WAV
        return "wav"
    if data[4:8] == b"ftyp":                                  # MP4 / M4A
        return "m4a"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):  # MP3
        return "mp3"
    if data[:4] == b"\x1a\x45\xdf\xa3":                       # WebM / Matroska
        return "webm"
    return None


def _looks_like_audio(data: bytes) -> bool:
    return _sniff_format(data) is not None

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
        "upload_token":  create_upload_token(session.id, user_id),
        "status":        session.status,
        "started_at":    session.started_at.isoformat(),
    }


# ── POST /sessions/{session_id}/chunks ─────────────────────────────────────────

@router.post("/{session_id}/chunks", status_code=202)
async def upload_chunk(
    session_id: str,
    # Upper bound is a sanity guard, not a real limit: 20000 chunks at 30 s is
    # ~7 days of continuous recording, far beyond any single night.
    chunk_index: int      = Form(..., ge=0, le=20000),
    duration_seconds: int = Form(..., ge=1, le=300),
    audio: UploadFile     = File(...),
    user_id: str          = Depends(get_current_user_id),
    x_upload_token: str | None = Header(None, alias="X-Upload-Token"),
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

    # Reject malformed session IDs early (catches test-only strings like "non-existent-session-id").
    if not _UUID_RE.match(session_id):
        raise HTTPException(status_code=404, detail="Session not found or not in recording state")

    # Look up the session regardless of user to distinguish "wrong user" from "not found".
    existing = db.query(SleepSession).filter(SleepSession.id == session_id).first()
    if existing:
        # Session exists: enforce ownership and recording state.
        if existing.user_id != user_id or existing.status != "recording":
            raise HTTPException(status_code=404, detail="Session not found or not in recording state")
        session = existing
    else:
        # Unknown session: it was created elsewhere (analytics-service). Only create
        # the ingestion-side record if the caller presents a valid session-scoped
        # upload token bound to (session_id, user_id) — otherwise any authenticated
        # user could claim an arbitrary session_id (the upload token is the proof of
        # legitimate session creation, replacing the old blind shadow-create).
        if not x_upload_token:
            raise HTTPException(status_code=403, detail="Upload token required to create this session")
        token_uid = verify_upload_token(x_upload_token, session_id)
        if token_uid != user_id:
            raise HTTPException(status_code=403, detail="Upload token does not belong to this user")
        session = SleepSession(
            id=session_id,
            user_id=user_id,
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            status="recording",
        )
        db.add(session)
        db.flush()

    # Reject duplicates, but ALLOW gaps.
    #
    # This previously required chunk_index == count(), so a single dropped upload
    # poisoned the rest of the session: the client increments the index on a
    # 30-second timer and does not retry, so one network blip five minutes into
    # an eight-hour night made every subsequent chunk fail the equality check —
    # roughly 950 chunks silently discarded, with the temp WAVs already deleted.
    #
    # Ordering is reconstructed from chunk_index at read time, so a gap is
    # harmless; only a repeated index is a genuine conflict. The
    # (session_id, chunk_index) unique constraint on AudioChunk enforces that at
    # the database level regardless, making the old count() check redundant as
    # well as harmful.
    duplicate = db.query(AudioChunk).filter(
        AudioChunk.session_id == session_id,
        AudioChunk.chunk_index == chunk_index,
    ).first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"chunk_index {chunk_index} has already been uploaded for this session",
        )

    # Reject oversized uploads via the declared size before buffering the body.
    if audio.size is not None and audio.size > MAX_CHUNK_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio chunk exceeds maximum size of {settings.MAX_CHUNK_SIZE_MB} MB",
        )

    # Read body and enforce size limit
    audio_bytes = await audio.read()
    file_size = len(audio_bytes)
    if file_size > MAX_CHUNK_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio chunk exceeds maximum size of {settings.MAX_CHUNK_SIZE_MB} MB",
        )

    # Validate the actual bytes, not just the spoofable Content-Type header.
    audio_ext = _sniff_format(audio_bytes)
    if audio_ext is None:
        raise HTTPException(status_code=400, detail="Uploaded data is not a recognised audio format")

    # Extension comes from the sniffed container, not a hardcoded ".opus". The
    # mobile client currently uploads WAV (assembled from the PCM stream in
    # RecordScreen.flushChunk), so keys used to be named .opus while holding
    # WAV bytes — anything resolving the format from the key was misled.
    s3_key = f"{user_id}/{session_id}/chunk_{chunk_index:03d}.{audio_ext}"
    stored = s3_upload(BytesIO(audio_bytes), s3_key, content_type)
    if not stored:
        # Best-effort by design: the row is still written so the chunk is
        # accounted for, but say so rather than logging success.
        _logger.warning("chunk %s recorded but NOT stored — object storage unavailable", s3_key)

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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Chunk {chunk_index} already uploaded for this session")

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
    # Enforce ownership BEFORE serving from cache — otherwise any authenticated
    # user who knows a session_id could read another user's processing status.
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id,
        SleepSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Redis cache hit (only reached after ownership is confirmed)
    cached = get_session_status(session_id)
    if cached:
        return cached

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


# ── DELETE /sessions/{session_id}/audio ────────────────────────────────────────

@router.delete("/{session_id}/audio", status_code=200)
def delete_audio(
    session_id: str,
    user_id: str    = Depends(get_current_user_id),
    db: Session     = Depends(get_db),
):
    """Delete raw audio files from S3 while preserving chunk metadata (FR-PRIV-002)."""
    session = db.query(SleepSession).filter(
        SleepSession.id == session_id,
        SleepSession.user_id == user_id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    deleted = s3_delete_session(user_id, session_id)

    # Null out S3 keys so downstream knows audio is gone
    db.query(AudioChunk).filter(AudioChunk.session_id == session_id).update(
        {"s3_key": None}, synchronize_session=False
    )
    db.commit()

    return {"session_id": session_id, "objects_deleted": deleted, "audio_deleted": True}
