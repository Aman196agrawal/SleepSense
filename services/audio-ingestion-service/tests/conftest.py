import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt

from app.main import app
from app.database import Base, get_db
import app.routes.sessions as _sessions_mod

TEST_DB_URL = "sqlite:///:memory:"
TEST_SECRET  = "dev-secret-key-change-in-production"

engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.create_all(bind=engine)
    _sessions_mod._chunk_rl.clear()
    yield
    Base.metadata.drop_all(bind=engine)
    _sessions_mod._chunk_rl.clear()


@pytest.fixture(autouse=True)
def mock_s3():
    """Prevent real S3 calls in every test."""
    with patch("app.routes.sessions.s3_upload", return_value=True):
        yield


@pytest.fixture
def client():
    return TestClient(app)


def _make_token(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "type": "access"}, TEST_SECRET, algorithm="HS256")


@pytest.fixture
def user_id() -> str:
    return "test-user-uuid-001"


@pytest.fixture
def auth_headers(user_id):
    return {"Authorization": f"Bearer {_make_token(user_id)}"}


@pytest.fixture
def other_auth_headers():
    return {"Authorization": f"Bearer {_make_token('other-user-uuid-002')}"}


@pytest.fixture
def active_session(client, auth_headers):
    """Start a session and return its session_id."""
    resp = client.post("/sessions", headers=auth_headers)
    assert resp.status_code == 201
    return resp.json()["session_id"]


def _fake_audio(size_bytes: int = 512) -> bytes:
    return b"\x00" * size_bytes


def _upload(client, session_id, auth_headers, chunk_index=0, duration=30, size=512):
    from io import BytesIO
    return client.post(
        f"/sessions/{session_id}/chunks",
        files={"audio": ("chunk.opus", BytesIO(_fake_audio(size)), "audio/opus")},
        data={"chunk_index": str(chunk_index), "duration_seconds": str(duration)},
        headers=auth_headers,
    )
