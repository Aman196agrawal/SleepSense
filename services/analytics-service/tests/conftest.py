import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from jose import jwt

from app.main import app
from app.database import Base, get_db
from app.config import settings

TEST_DB_URL = "sqlite:///:memory:"

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
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def make_access_token(user_id: str) -> str:
    """Create a valid SleepSense JWT for the given user_id."""
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=60)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access"},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


@pytest.fixture
def user_a_id():
    return "user-a-0000-0000-0000-000000000001"


@pytest.fixture
def user_b_id():
    return "user-b-0000-0000-0000-000000000002"


@pytest.fixture
def headers_a(user_a_id):
    return {"Authorization": f"Bearer {make_access_token(user_a_id)}"}


@pytest.fixture
def headers_b(user_b_id):
    return {"Authorization": f"Bearer {make_access_token(user_b_id)}"}
