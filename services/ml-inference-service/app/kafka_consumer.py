"""
Kafka consumer loop — runs in a background thread from main.py.
Consumes audio.chunk.uploaded → runs ML pipeline → emits analysis.complete.
"""
import json
import logging

_logger = logging.getLogger(__name__)


def run_consumer(classifier, regressor, db_factory, influx_write_api, kafka_emit):
    """
    Blocking consumer loop. Intended to run in a daemon thread.
    Exits on unrecoverable errors so the process can restart cleanly.
    """
    from app.config import settings
    from app.worker import process_chunk
    from app.s3_client import download_audio

    try:
        from kafka import KafkaConsumer
    except ImportError:
        _logger.warning("kafka-python not installed — consumer disabled")
        return

    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        _logger.info("KAFKA_BOOTSTRAP_SERVERS not set — consumer disabled")
        return

    consumer = KafkaConsumer(
        settings.KAFKA_INPUT_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode()),
        group_id=settings.KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    _logger.info("Kafka consumer started on topic %s", settings.KAFKA_INPUT_TOPIC)

    for msg in consumer:
        payload = msg.value
        chunk_id = payload.get("chunk_id", "<unknown>")
        try:
            audio_bytes = download_audio(payload["s3_key"])
            if not audio_bytes:
                _logger.error("Empty audio for chunk %s — skipping", chunk_id)
                continue

            db = db_factory()
            try:
                process_chunk(
                    chunk_id=chunk_id,
                    session_id=payload["session_id"],
                    user_id=payload["user_id"],
                    audio_bytes=audio_bytes,
                    chunk_index=int(payload["chunk_index"]),
                    duration_seconds=int(payload.get("duration_seconds", 30)),
                    classifier=classifier,
                    regressor=regressor,
                    db=db,
                    influx_write=influx_write_api,
                    kafka_emit=kafka_emit,
                )
            finally:
                db.close()

        except Exception as exc:
            _logger.error("Failed to process chunk %s: %s", chunk_id, exc, exc_info=True)
