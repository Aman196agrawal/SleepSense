import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.routes import sessions, analytics, insights, lifestyle
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
app.include_router(ws_router, tags=["WebSocket"])

@app.get("/health")
def health():
    return {"status": "ok", "service": "analytics-service"}
