import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, ForeignKey
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
    weight_kg     = Column(Float, nullable=True)
    height_cm     = Column(Float, nullable=True)
    timezone              = Column(String, default="Asia/Kolkata")
    bedtime_reminder_time = Column(String, nullable=True)
    is_active             = Column(Boolean, default=True)
    is_verified   = Column(Boolean, default=False)
    role          = Column(String, default="user")   # user | admin | researcher
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

class UserHealthProfile(Base):
    __tablename__ = "user_health_profile"

    id                    = Column(String, primary_key=True, default=gen_uuid)
    user_id               = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    sleep_position        = Column(String, nullable=True)       # back/side/stomach
    known_conditions      = Column(String, nullable=True)       # JSON-encoded list
    medications           = Column(String, nullable=True)       # JSON-encoded list
    alcohol_frequency     = Column(String, nullable=True)       # never/occasionally/regularly
    smoking_status        = Column(String, nullable=True)       # never/former/current
    cpap_user             = Column(Boolean, nullable=True)
    snoring_severity_self = Column(Integer, nullable=True)      # 1–5
    updated_at            = Column(DateTime, default=_utcnow, onupdate=_utcnow)

class SocialAccount(Base):
    __tablename__ = "social_accounts"

    id           = Column(String, primary_key=True, default=gen_uuid)
    user_id      = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider     = Column(String, nullable=False)               # google/apple
    provider_uid = Column(String, nullable=False, unique=True)
    created_at   = Column(DateTime, default=_utcnow)

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id         = Column(String, primary_key=True, default=gen_uuid)
    user_id    = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_used    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)

class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id         = Column(String, primary_key=True, default=gen_uuid)
    user_id    = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token      = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    is_used    = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_utcnow)
