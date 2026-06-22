from sqlalchemy import create_engine, text
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


def _run_migrations(eng):
    """Add columns that don't exist yet (SQLite ALTER TABLE is limited)."""
    stmts = [
        "ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0",
        "ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'",
        "ALTER TABLE users ADD COLUMN bedtime_reminder_time VARCHAR",
    ]
    with eng.connect() as conn:
        for stmt in stmts:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception as exc:
                conn.rollback()
                # Only "column already exists" is expected/ignorable; surface anything
                # else instead of silently hiding a genuine migration failure.
                msg = str(exc).lower()
                if "duplicate column" not in msg and "already exists" not in msg:
                    import logging
                    logging.getLogger(__name__).warning("Migration step failed: %s (%s)", stmt, exc)


_run_migrations(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
