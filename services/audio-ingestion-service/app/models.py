import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def gen_uuid():
    return str(uuid.uuid4())


class SleepSession(Base):
    """Ingestion-service view of a session: tracks recording state and raw chunk metadata."""
    __tablename__ = "sleep_sessions"

    id               = Column(String, primary_key=True, default=gen_uuid)
    user_id          = Column(String, nullable=False, index=True)
    started_at       = Column(DateTime, nullable=False)
    ended_at         = Column(DateTime, nullable=True)
    status           = Column(String, default="recording")  # recording|processing|complete|failed
    total_chunks     = Column(Integer, default=0)
    notes            = Column(String, nullable=True)
    room_temperature = Column(Float, nullable=True)
    created_at       = Column(DateTime, default=_utcnow)
    updated_at       = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class AudioChunk(Base):
    """One 30-second audio upload within a session."""
    __tablename__ = "audio_chunks"

    id               = Column(String, primary_key=True, default=gen_uuid)
    session_id       = Column(String, ForeignKey("sleep_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index      = Column(Integer, nullable=False)
    s3_key           = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=False)
    file_size_bytes  = Column(Integer, nullable=False)
    content_type     = Column(String, nullable=True)
    status           = Column(String, default="pending")  # pending|processing|done|failed
    created_at       = Column(DateTime, default=_utcnow)
    processed_at     = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("session_id", "chunk_index", name="uq_session_chunk"),
    )
