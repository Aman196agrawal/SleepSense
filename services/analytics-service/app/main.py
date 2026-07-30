import hmac
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, SessionLocal, get_db
from app.models import SleepSession, TimelineBucket, SessionInsight, LifestyleLog, UserGoal, SeededUser
from app.routes import sessions, analytics, insights, lifestyle, goals
from app.routes.ws import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

Base.metadata.create_all(bind=engine)


def _add_missing_columns() -> None:
    """Add columns that exist on the models but not yet in the database.

    create_all() only creates missing *tables*, so a new column on an existing
    table is invisible to it and every query referencing that column fails.
    There is no migration tool wired up here, and the local databases hold real
    session history worth keeping, so add them in place. Idempotent, and each
    ALTER is isolated so one failure cannot block the rest.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            ddl_type = column.type.compile(dialect=engine.dialect)
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {ddl_type}'
                    ))
                logging.getLogger(__name__).info(
                    "added missing column %s.%s (%s)", table.name, column.name, ddl_type
                )
            except Exception:
                logging.getLogger(__name__).warning(
                    "could not add column %s.%s", table.name, column.name, exc_info=True
                )


_add_missing_columns()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.kafka_consumer import run_consumer
    from app.kafka_client import emit

    t = threading.Thread(
        target=run_consumer,
        args=(SessionLocal, emit),
        daemon=True,
        name="analytics-kafka-consumer",
    )
    t.start()
    yield


app = FastAPI(title="SleepSense — Analytics Service", version="1.0.0", lifespan=lifespan)

_origins = [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]
_wildcard = _origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # The CORS spec rejects "*" + credentials. Drop credentials when wildcarding.
    allow_credentials=not _wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router,   prefix="/sessions",  tags=["Sessions"])
app.include_router(analytics.router,  prefix="/analytics", tags=["Analytics"])
app.include_router(insights.router,   prefix="/insights",  tags=["Insights"])
app.include_router(lifestyle.router,  prefix="/lifestyle", tags=["Lifestyle"])
app.include_router(goals.router,      prefix="/goals",     tags=["Goals"])
app.include_router(ws_router, tags=["WebSocket"])

@app.delete("/internal/users/{user_id}", status_code=204, include_in_schema=False)
def purge_user_data(
    user_id: str,
    x_internal_secret: str | None = Header(None, alias="X-Internal-Secret"),
    db: Session = Depends(get_db),
):
    """Internal endpoint — called by auth-service on account deletion to purge analytics data.
    Protected by a shared secret header — never call from untrusted clients."""
    if not settings.INTERNAL_API_SECRET or not hmac.compare_digest(x_internal_secret or "", settings.INTERNAL_API_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    db.query(UserGoal).filter(UserGoal.user_id == user_id).delete()
    db.query(LifestyleLog).filter(LifestyleLog.user_id == user_id).delete()
    db.query(SessionInsight).filter(SessionInsight.user_id == user_id).delete()
    session_ids = [s.id for s in db.query(SleepSession.id).filter(SleepSession.user_id == user_id).all()]
    if session_ids:
        db.query(TimelineBucket).filter(TimelineBucket.session_id.in_(session_ids)).delete(synchronize_session=False)
    db.query(SleepSession).filter(SleepSession.user_id == user_id).delete()
    db.query(SeededUser).filter(SeededUser.user_id == user_id).delete()
    db.commit()
    from fastapi import Response
    return Response(status_code=204)


@app.get("/internal/users/{user_id}/recent-scores", include_in_schema=False)
def get_recent_scores(
    user_id: str,
    limit: int = 5,
    x_internal_secret: str | None = Header(None, alias="X-Internal-Secret"),
    db: Session = Depends(get_db),
):
    """Internal — returns the N most recent sleep quality scores for health alert logic."""
    if not settings.INTERNAL_API_SECRET or not hmac.compare_digest(x_internal_secret or "", settings.INTERNAL_API_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")
    rows = (
        db.query(SleepSession.sleep_quality_score)
        .filter(SleepSession.user_id == user_id, SleepSession.status == "complete")
        .order_by(SleepSession.started_at.desc())
        .limit(limit)
        .all()
    )
    return {"scores": [r[0] for r in rows if r[0] is not None]}


@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}

@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database not ready")
    return {"status": "ready", "service": "analytics-service", "db": "ok"}
