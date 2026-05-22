import logging

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db
from app.routes import sessions, analytics, insights, lifestyle, goals
from app.routes.ws import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SleepSense — Analytics Service", version="1.0.0")

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
