import json
from app.config import settings

_producer = None

def get_producer():
    """Return Kafka producer if KAFKA_BOOTSTRAP_SERVERS is configured, else None."""
    global _producer
    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        return None
    if _producer is None:
        try:
            from kafka import KafkaProducer
            _producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                request_timeout_ms=5000,
                retries=3,
            )
        except Exception:
            return None
    return _producer

def emit(topic: str, payload: dict) -> None:
    """Best-effort event publish — never raises."""
    p = get_producer()
    if p:
        try:
            p.send(topic, payload)
            p.flush()
        except Exception:
            pass
