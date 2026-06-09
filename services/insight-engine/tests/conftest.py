"""Shared fixtures for the insight engine test suite."""
import os

# Required env vars must be set before app.config is imported anywhere.
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-prod-32chars")

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import SessionInsight
from app.security import get_current_user_id

TEST_DB_URL   = "sqlite:///:memory:"
engine        = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_USER_ID  = "user-test-001"
OTHER_USER_ID = "user-test-002"
SESSION_ID    = "session-aaa-111"


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
def client(db):
    def _override_db():
        yield db

    def _override_auth():
        return TEST_USER_ID

    app.dependency_overrides[get_db]              = _override_db
    app.dependency_overrides[get_current_user_id] = _override_auth

    with patch("app.main.init_db"), TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ── DB helpers ────────────────────────────────────────────────────────────────

def make_insight(db, session_id=SESSION_ID, user_id=TEST_USER_ID, **kwargs) -> SessionInsight:
    defaults = dict(
        session_id   = session_id,
        user_id      = user_id,
        insight_type = "tip",
        priority     = 5,
        title        = "Test Insight",
        body         = "This is a test insight body.",
        action_url   = "sleepsense://tips/test",
        is_read      = False,
    )
    defaults.update(kwargs)
    ins = SessionInsight(**defaults)
    db.add(ins)
    db.commit()
    db.refresh(ins)
    return ins


# ── Reusable generate payloads ────────────────────────────────────────────────

def good_session_payload(session_id=SESSION_ID):
    """A session that fires no rules."""
    return {
        "session_id":          session_id,
        "sleep_quality_score": 80.0,
        "snore_ratio":         0.2,
        "avg_snore_intensity": 30.0,
        "duration_minutes":    480,
        "recent_scores":       [75.0, 78.0, 80.0],
        "recent_durations":    [480, 490, 470],
        "alcohol_units_today": 0.0,
        "sleep_position":      "side",
    }


def chronic_snoring_payload(session_id=SESSION_ID):
    """A session that fires CHRONIC_SNORING (5 consecutive poor nights)."""
    return {
        "session_id":          session_id,
        "sleep_quality_score": 40.0,
        "snore_ratio":         0.7,
        "avg_snore_intensity": 75.0,
        "duration_minutes":    360,
        "recent_scores":       [45.0, 42.0, 38.0, 41.0, 44.0],
        "recent_durations":    [360, 340, 380, 350, 360],
        "alcohol_units_today": 0.0,
        "sleep_position":      "side",
    }
