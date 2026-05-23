import json
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response

from app.classifier import SnoreClassifier
from app.config import settings
from app.database import SessionLocal, init_db
from app.influx_client import get_influx_write_api
from app.kafka_producer import _get_producer, emit
from app.regressor import IntensityRegressor

_logger = logging.getLogger(__name__)

classifier = SnoreClassifier()
regressor  = IntensityRegressor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    # Load models (if paths are configured; otherwise stubs are used)
    if settings.CLASSIFIER_MODEL_PATH:
        classifier.load(settings.CLASSIFIER_MODEL_PATH)
    if settings.REGRESSOR_MODEL_PATH:
        regressor.load(settings.REGRESSOR_MODEL_PATH)

    _logger.info(
        "Classifier: %s | Regressor: %s",
        "stub" if classifier.is_stub else "model",
        "stub" if regressor.is_stub  else "model",
    )

    # Start Kafka consumer in a daemon thread
    from app.kafka_consumer import run_consumer
    t = threading.Thread(
        target=run_consumer,
        args=(classifier, regressor, SessionLocal, get_influx_write_api(), emit),
        daemon=True,
        name="kafka-consumer",
    )
    t.start()

    yield


app = FastAPI(
    title="SleepSense ML Inference Service",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    checks: dict = {
        "classifier": "stub" if classifier.is_stub else "model",
        "regressor":  "stub" if regressor.is_stub  else "model",
    }

    # DB
    try:
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # InfluxDB
    try:
        if settings.INFLUXDB_URL:
            from influxdb_client import InfluxDBClient
            InfluxDBClient(
                url=settings.INFLUXDB_URL,
                token=settings.INFLUXDB_TOKEN,
                org=settings.INFLUXDB_ORG,
            ).ping()
            checks["influxdb"] = "ok"
        else:
            checks["influxdb"] = "not_configured"
    except Exception:
        checks["influxdb"] = "error"

    # Kafka
    try:
        checks["kafka"] = "ok" if _get_producer() else "unavailable"
    except Exception:
        checks["kafka"] = "unavailable"

    # S3
    try:
        if settings.S3_BUCKET:
            import boto3
            boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL or None,
                aws_access_key_id=settings.S3_ACCESS_KEY or None,
                aws_secret_access_key=settings.S3_SECRET_KEY or None,
                region_name=settings.S3_REGION,
            ).head_bucket(Bucket=settings.S3_BUCKET)
            checks["s3"] = "ok"
        else:
            checks["s3"] = "not_configured"
    except Exception:
        checks["s3"] = "error"

    # Redis
    try:
        from app.redis_client import check_connectivity
        checks["redis"] = "ok" if check_connectivity() else "unavailable"
    except Exception:
        checks["redis"] = "unavailable"

    failed = [k for k, v in checks.items() if v == "error"]
    if failed:
        return Response(
            content=json.dumps({"status": "not_ready", "checks": checks}),
            status_code=503,
            media_type="application/json",
        )
    return {"status": "ready", "checks": checks}
