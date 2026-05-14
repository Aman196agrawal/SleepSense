import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import SessionLocal, init_db
from app.dispatcher import dispatch

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from app.kafka_consumer import run_consumer
    t = threading.Thread(
        target=run_consumer,
        args=(SessionLocal, dispatch),
        daemon=True,
        name="notif-kafka-consumer",
    )
    t.start()

    yield


app = FastAPI(
    title="SleepSense Notification Service",
    version="1.0.0",
    lifespan=lifespan,
)

from app.routes import notifications, device_tokens  # noqa: E402

app.include_router(notifications.router,  prefix="/notifications",  tags=["Notifications"])
app.include_router(device_tokens.router,  prefix="/device-tokens",  tags=["Device Tokens"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}
