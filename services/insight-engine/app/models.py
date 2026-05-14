import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def gen_uuid():
    return str(uuid.uuid4())


class SessionInsight(Base):
    __tablename__ = "session_insights"

    id           = Column(String, primary_key=True, default=gen_uuid)
    session_id   = Column(String, nullable=False, index=True)
    user_id      = Column(String, nullable=False, index=True)
    insight_type = Column(String, nullable=False)   # tip | warning | achievement
    priority     = Column(Integer, default=0)
    title        = Column(String, nullable=False)
    body         = Column(String, nullable=False)
    action_url   = Column(String, nullable=True)
    is_read      = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=_utcnow)
