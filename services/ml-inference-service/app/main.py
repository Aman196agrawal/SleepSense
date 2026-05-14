import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.classifier import SnoreClassifier
from app.config import settings
from app.database import SessionLocal, init_db
from app.influx_client import get_influx_write_api
from app.kafka_producer import emit
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
    return {
        "status":     "ready",
        "classifier": "stub" if classifier.is_stub else "model",
        "regressor":  "stub" if regressor.is_stub  else "model",
    }
