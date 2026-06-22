"""
Kafka consumer loop — runs in a background thread from main.py.
Consumes audio.chunk.uploaded → runs ML pipeline → emits analysis.complete.
"""
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def _parse_ts(ts: str | None):
    """Parse the ISO upload timestamp from the event payload, or None."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


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
        # Commit offsets manually, only after a chunk is fully processed (or
        # explicitly marked failed), so a crash mid-processing replays the chunk
        # instead of silently skipping it.
        enable_auto_commit=False,
    )
    _logger.info("Kafka consumer started on topic %s", settings.KAFKA_INPUT_TOPIC)

    for msg in consumer:
        payload = msg.value
        chunk_id = payload.get("chunk_id", "<unknown>")
        try:
            audio_bytes = download_audio(payload["s3_key"])
            if not audio_bytes:
                _logger.error("Empty audio for chunk %s — marking failed", chunk_id)
                _mark_chunk_failed(db_factory, kafka_emit, payload, "empty audio")
                consumer.commit()
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
                    chunk_started_at=_parse_ts(payload.get("timestamp")),
                )
            finally:
                db.close()

            # Success — advance the offset.
            consumer.commit()

        except Exception as exc:
            _logger.error("Failed to process chunk %s: %s", chunk_id, exc, exc_info=True)
            # Record the failure so the chunk doesn't sit "pending" forever and the
            # session can still reach 100%, then move past this (poison) message.
            _mark_chunk_failed(db_factory, kafka_emit, payload, str(exc))
            consumer.commit()


def _mark_chunk_failed(db_factory, kafka_emit, payload: dict, reason: str) -> None:
    """Mark a chunk failed in the DB and emit a terminal analysis.complete event
    (empty summary) so the downstream session-completion counter still advances."""
    chunk_id = payload.get("chunk_id")
    try:
        from app.models import AudioChunk
        db = db_factory()
        try:
            chunk = db.query(AudioChunk).filter(AudioChunk.id == chunk_id).first()
            if chunk:
                chunk.status = "failed"
                db.commit()
        finally:
            db.close()
    except Exception as exc:
        _logger.warning("Could not mark chunk %s failed: %s", chunk_id, exc)

    try:
        kafka_emit("analysis.complete", {
            "chunk_id":    chunk_id,
            "session_id":  payload.get("session_id"),
            "user_id":     payload.get("user_id"),
            "chunk_index": payload.get("chunk_index"),
            "summary":     {"failed": True, "reason": reason, "total_windows": 0,
                            "snore_windows": 0, "snore_ratio": 0.0, "avg_intensity": 0.0},
        })
    except Exception as exc:
        _logger.warning("Could not emit failure event for chunk %s: %s", chunk_id, exc)
