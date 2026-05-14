import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, DateTime, ForeignKey, JSON
from app.database import Base

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def gen_uuid():
    return str(uuid.uuid4())

class SleepSession(Base):
    __tablename__ = "sleep_sessions"

    id                   = Column(String, primary_key=True, default=gen_uuid)
    user_id              = Column(String, nullable=False, index=True)
    started_at           = Column(DateTime, nullable=False)
    ended_at             = Column(DateTime, nullable=True)
    duration_minutes     = Column(Integer, nullable=True)
    status               = Column(String, default="recording")  # recording|processing|complete|failed
    sleep_quality_score  = Column(Float, nullable=True)
    sleep_quality_grade  = Column(String, nullable=True)
    snoring_duration_min = Column(Integer, nullable=True)
    snoring_percentage   = Column(Float, nullable=True)
    snore_events_per_hour= Column(Float, nullable=True)
    avg_snore_intensity  = Column(Float, nullable=True)
    max_snore_intensity  = Column(Float, nullable=True)
    peak_snoring_hour    = Column(Integer, nullable=True)
    total_chunks         = Column(Integer, default=0)
    processed_chunks     = Column(Integer, default=0)
    notes                = Column(String, nullable=True)
    created_at           = Column(DateTime, default=_utcnow)

class TimelineBucket(Base):
    __tablename__ = "timeline_buckets"

    id                = Column(String, primary_key=True, default=gen_uuid)
    session_id        = Column(String, ForeignKey("sleep_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    bucket_index      = Column(Integer, nullable=False)
    offset_minutes    = Column(Integer, nullable=False)
    avg_intensity     = Column(Float, default=0.0)
    dominant_class    = Column(String, default="silence")
    snore_event_count = Column(Integer, default=0)

class SessionInsight(Base):
    __tablename__ = "session_insights"

    id           = Column(String, primary_key=True, default=gen_uuid)
    session_id   = Column(String, ForeignKey("sleep_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id      = Column(String, nullable=False, index=True)
    insight_type = Column(String, nullable=False)  # tip|warning|achievement
    priority     = Column(Integer, default=0)
    title        = Column(String, nullable=False)
    body         = Column(String, nullable=False)
    is_read      = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=_utcnow)

class LifestyleLog(Base):
    __tablename__ = "lifestyle_logs"

    id               = Column(String, primary_key=True, default=gen_uuid)
    user_id          = Column(String, nullable=False, index=True)
    logged_date      = Column(String, nullable=False)
    alcohol_units    = Column(Float, default=0.0)
    exercise_minutes = Column(Integer, default=0)
    stress_level     = Column(Integer, default=3)
    caffeine_cups    = Column(Integer, default=0)
    sleep_aid_used   = Column(Boolean, default=False)
    notes            = Column(String, nullable=True)
    created_at       = Column(DateTime, default=_utcnow)

class SeededUser(Base):
    __tablename__ = "seeded_users"
    user_id    = Column(String, primary_key=True)
    seeded_at  = Column(DateTime, default=_utcnow)
