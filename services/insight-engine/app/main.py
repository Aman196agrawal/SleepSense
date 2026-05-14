import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import SessionLocal, init_db
from app.kafka_producer import emit

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from app.kafka_consumer import run_consumer
    t = threading.Thread(
        target=run_consumer,
        args=(SessionLocal, emit),
        daemon=True,
        name="insight-kafka-consumer",
    )
    t.start()

    yield


app = FastAPI(
    title="SleepSense Insight Engine",
    version="1.0.0",
    lifespan=lifespan,
)

from app.routes import insights  # noqa: E402

app.include_router(insights.router, prefix="/insights", tags=["Insights"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "insight-engine"}
