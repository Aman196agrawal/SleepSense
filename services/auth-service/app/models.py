import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from app.database import Base

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def gen_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id            = Column(String, primary_key=True, default=gen_uuid)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)
    display_name  = Column(String, nullable=True)
    weight_kg     = Column(String, nullable=True)
    height_cm     = Column(String, nullable=True)
    timezone      = Column(String, default="Asia/Kolkata")
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=_utcnow)
    updated_at    = Column(DateTime, default=_utcnow, onupdate=_utcnow)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(String, primary_key=True, default=gen_uuid)
    user_id    = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_revoked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
