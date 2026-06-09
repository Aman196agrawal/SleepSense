from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import init_db, engine
from app.routes import sessions
from app.routes import admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="SleepSense Audio Ingestion Service", version="1.0.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "audio-ingestion-service"}


@app.get("/ready")
def ready():
    """Readiness probe: verifies DB, S3, and Kafka are reachable."""
    checks: dict[str, str] = {}

    # Database
    try:
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"

    # S3
    try:
        from app.s3_client import check_connectivity
        checks["s3"] = "ok" if check_connectivity() else "unavailable"
    except Exception as exc:
        checks["s3"] = f"error: {exc}"

    # Kafka (optional — not a hard dependency)
    try:
        from app.kafka_client import _get_producer
        checks["kafka"] = "ok" if _get_producer() is not None else "unavailable"
    except Exception as exc:
        checks["kafka"] = f"error: {exc}"

    failed = [k for k, v in checks.items() if v not in ("ok", "unavailable")]
    if failed:
        from fastapi import Response
        return Response(
            content=__import__("json").dumps({"status": "not_ready", "checks": checks}),
            status_code=503,
            media_type="application/json",
        )
    return {"status": "ready", "checks": checks}


app.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
app.include_router(admin.router, prefix="/internal", tags=["internal"])
