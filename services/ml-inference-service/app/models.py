from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, UniqueConstraint
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AudioChunk(Base):
    """ML service's view of an audio chunk — read s3_key, write status + result."""
    __tablename__ = "audio_chunks"

    id               = Column(String, primary_key=True)
    session_id       = Column(String, nullable=False, index=True)
    chunk_index      = Column(Integer, nullable=False)
    s3_key           = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=False, default=30)
    file_size_bytes  = Column(Integer, nullable=False, default=0)
    content_type     = Column(String, nullable=True)
    status           = Column(String, default="pending")  # pending|processing|done|failed
    analysis_result  = Column(String, nullable=True)      # JSON string
    created_at       = Column(DateTime, default=_utcnow)
    processed_at     = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("session_id", "chunk_index", name="uq_session_chunk"),
    )
