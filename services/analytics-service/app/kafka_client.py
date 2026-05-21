import json
import logging
from functools import lru_cache
from typing import Optional

from app.config import settings

_logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _build_producer():
    """Construct the Kafka producer once. Returns None if Kafka isn't configured
    or if the broker is unreachable at startup."""
    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        return None
    try:
        from kafka import KafkaProducer
        return KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=5000,
            retries=3,
        )
    except Exception:
        _logger.warning(
            "Failed to initialise Kafka producer (bootstrap=%s)",
            settings.KAFKA_BOOTSTRAP_SERVERS, exc_info=True,
        )
        return None


def get_producer() -> Optional[object]:
    """Return cached Kafka producer if configured, else None."""
    return _build_producer()


def emit(topic: str, payload: dict) -> None:
    """Best-effort event publish — never raises, but logs failures."""
    p = get_producer()
    if not p:
        return
    try:
        p.send(topic, payload)
        p.flush()
    except Exception:
        _logger.warning("Kafka publish failed for topic=%s", topic, exc_info=True)
