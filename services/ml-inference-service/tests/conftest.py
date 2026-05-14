"""Shared fixtures for the ML inference service test suite."""
import io
import wave

import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import AudioChunk

SR = 16_000


def make_wav(duration: float = 3.0, freq: float = 440.0, amplitude: float = 0.5) -> bytes:
    """Generate a synthetic sine-wave WAV file in memory."""
    n      = int(duration * SR)
    t      = np.linspace(0, duration, n, endpoint=False)
    signal = (np.sin(2 * np.pi * freq * t) * amplitude * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(signal.tobytes())
    return buf.getvalue()


def make_wav_silence(duration: float = 3.0) -> bytes:
    """Generate near-silent WAV (very low amplitude)."""
    return make_wav(duration=duration, amplitude=0.001)


def make_wav_loud(duration: float = 3.0) -> bytes:
    """Generate loud WAV (high amplitude, simulates snoring)."""
    return make_wav(duration=duration, amplitude=0.95)


# ── DB fixture ─────────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite:///:memory:"
engine       = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_with_chunk(db):
    """DB session with one pending AudioChunk pre-inserted."""
    chunk = AudioChunk(
        id="chunk-001",
        session_id="session-001",
        chunk_index=0,
        s3_key="user1/session-001/chunk_000.opus",
        duration_seconds=30,
        file_size_bytes=512,
        status="pending",
    )
    db.add(chunk)
    db.commit()
    return db
