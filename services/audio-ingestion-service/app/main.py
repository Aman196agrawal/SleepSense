from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db
from app.routes import sessions


@asynccontextmanager
async def lifespan(app):
    init_db()
    yield


app = FastAPI(title="SleepSense Audio Ingestion Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {"status": "ready"}


app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
