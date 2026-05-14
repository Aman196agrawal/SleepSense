"""Shared fixtures for the notification service test suite."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from unittest.mock import patch

from app.database import Base, get_db
from app.main import app
from app.models import DeviceToken, Notification
from app.security import get_current_user_id

TEST_DB_URL  = "sqlite:///:memory:"
engine       = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_USER_ID  = "user-test-001"
OTHER_USER_ID = "user-test-002"


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

    # prevent lifespan from touching the Docker-path production DB
    with patch("app.main.init_db"), TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ── DB helpers ────────────────────────────────────────────────────────────────

def make_notification(db, user_id=TEST_USER_ID, **kwargs) -> Notification:
    import json
    defaults = dict(
        user_id=user_id,
        type="sleep_report_ready",
        title="Your sleep report is ready.",
        body="Tap to see the full report.",
        payload=json.dumps({}),
        channel="push,in_app",
        is_read=False,
    )
    defaults.update(kwargs)
    n = Notification(**defaults)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def make_device_token(db, user_id=TEST_USER_ID, token="tok-abc123", platform="fcm") -> DeviceToken:
    dt = DeviceToken(user_id=user_id, token=token, platform=platform)
    db.add(dt)
    db.commit()
    db.refresh(dt)
    return dt
