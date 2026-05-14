import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, UniqueConstraint

from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def gen_uuid():
    return str(uuid.uuid4())


class DeviceToken(Base):
    __tablename__ = "device_tokens"

    id         = Column(String, primary_key=True, default=gen_uuid)
    user_id    = Column(String, nullable=False, index=True)
    token      = Column(String, nullable=False)
    platform   = Column(String, nullable=False)   # "fcm" | "apns"
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (UniqueConstraint("user_id", "token", name="uq_user_token"),)


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(String, primary_key=True, default=gen_uuid)
    user_id    = Column(String, nullable=False, index=True)
    type       = Column(String, nullable=False)   # sleep_report_ready|weekly_summary|health_alert|achievement
    title      = Column(String, nullable=False)
    body       = Column(String, nullable=False)
    payload    = Column(String, nullable=True)    # JSON string for deep-link data
    channel    = Column(String, nullable=False)   # comma-separated: push,in_app,email
    sent_at    = Column(DateTime, nullable=True)
    is_read    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
