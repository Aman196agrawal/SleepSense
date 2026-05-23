import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
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
def purge_user_data(user_id: str, db: Session = Depends(get_db)):
    """Internal endpoint — called by auth-service on account deletion to purge analytics data."""
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
