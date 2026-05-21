from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_pre_ping": True})

try:
    engine = create_engine(settings.DATABASE_URL, **_engine_kwargs)
except ModuleNotFoundError as e:
    raise RuntimeError(
        f"Could not load the database driver for DATABASE_URL={settings.DATABASE_URL!r}. "
        f"Install the matching driver (e.g. `pip install psycopg2-binary` for "
        f"Postgres) or switch back to the SQLite default."
    ) from e

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
