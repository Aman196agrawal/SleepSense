import json
import logging

_logger = logging.getLogger(__name__)
_producer = None


def _get_producer():
    global _producer
    if _producer is not None:
        return _producer
    try:
        from kafka import KafkaProducer
        from app.config import settings
        _producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode(),
        )
        return _producer
    except Exception as exc:
        _logger.debug("Kafka unavailable: %s", exc)
        return None


def emit(topic: str, payload: dict) -> None:
    producer = _get_producer()
    if producer:
        try:
            producer.send(topic, payload)
        except Exception as exc:
            _logger.warning("Kafka emit failed on %s: %s", topic, exc)
    else:
        _logger.debug("Kafka not available; skipping emit to %s", topic)
