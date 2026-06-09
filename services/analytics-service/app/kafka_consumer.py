"""
Kafka consumer for analysis.complete events from the ML Inference Service.
Updates session TimelineBuckets with real ML-derived results and, once all
chunks are processed, recomputes the session quality score.
Runs in a daemon thread started from main.py.
"""
import json
import logging
import uuid

_logger = logging.getLogger(__name__)


def run_consumer(db_factory, kafka_emit):
    from app.config import settings

    try:
        from kafka import KafkaConsumer
    except ImportError:
        _logger.warning("kafka-python not installed — analytics consumer disabled")
        return

    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        _logger.info("KAFKA_BOOTSTRAP_SERVERS not set — analytics consumer disabled")
        return

    consumer = KafkaConsumer(
        "analysis.complete",
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(","),
        value_deserializer=lambda v: json.loads(v.decode()),
        group_id=settings.KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    _logger.info("Analytics consumer started on topic analysis.complete")

    for msg in consumer:
        payload = msg.value
        session_id = payload.get("session_id", "<unknown>")
        try:
            _handle_analysis_complete(payload, db_factory, kafka_emit)
        except Exception as exc:
            _logger.error(
                "Failed to process analysis.complete for session %s: %s",
                session_id, exc, exc_info=True,
            )


def _safe_float(val, default: float = 0.0) -> float:
    try:
        return float(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _safe_int(val, default: int = 0) -> int:
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default


def _handle_analysis_complete(payload: dict, db_factory, kafka_emit):
    from app.models import SleepSession, TimelineBucket

    session_id = payload.get("session_id")
    user_id    = payload.get("user_id")
    if not session_id or not user_id:
        _logger.warning("Dropping malformed analysis.complete payload: missing session_id/user_id")
        return

    chunk_index = _safe_int(payload.get("chunk_index"), 0)
    summary     = payload.get("summary") or {}

    snore_ratio       = _safe_float(summary.get("snore_ratio"))
    avg_intensity     = _safe_float(summary.get("avg_intensity"))
    total_windows     = _safe_int(summary.get("total_windows"))
    snore_windows     = _safe_int(summary.get("snore_windows"))

    dominant_class    = "snoring" if snore_ratio >= 0.3 else (
        "breathing" if total_windows > 0 else "silence"
    )
    snore_event_count = snore_windows

    db = db_factory()
    try:
        # Update or create the TimelineBucket for this chunk (ML data is authoritative)
        bucket = db.query(TimelineBucket).filter(
            TimelineBucket.session_id == session_id,
            TimelineBucket.bucket_index == chunk_index,
        ).first()

        if bucket:
            bucket.avg_intensity     = round(avg_intensity, 1)
            bucket.dominant_class    = dominant_class
            bucket.snore_event_count = snore_event_count
        else:
            db.add(TimelineBucket(
                id=str(uuid.uuid4()),
                session_id=session_id,
                bucket_index=chunk_index,
                offset_minutes=chunk_index // 2,
                avg_intensity=round(avg_intensity, 1),
                dominant_class=dominant_class,
                snore_event_count=snore_event_count,
            ))

        session = db.query(SleepSession).filter(SleepSession.id == session_id).first()
        if not session:
            db.commit()
            return

        total = session.total_chunks or 0

        # Use Redis to atomically track how many ML events have arrived for this session.
        # Only recompute + notify when the last chunk's result lands — avoids duplicate
        # notifications and unnecessary DB writes.
        if session.status == "complete" and total > 0:
            ml_count = _increment_ml_counter(session_id)
            if ml_count is not None and ml_count >= total:
                db.commit()
                _recompute_and_notify(db_factory, session.id, session.user_id, kafka_emit)
                return

        db.commit()

    finally:
        db.close()


def _increment_ml_counter(session_id: str):
    """
    Atomically increment the per-session ML-complete counter in Redis.
    Returns the new count, or None if Redis is not available.
    """
    try:
        from app.config import settings
        if not settings.REDIS_URL:
            return None
        import redis as redis_lib
        r = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        key = f"ml_chunks:{session_id}"
        count = r.incr(key)
        if count == 1:
            r.expire(key, 86400)  # 24h TTL — long enough to cover any stragglers
        return int(count)
    except Exception as exc:
        _logger.debug("Redis ml_counter unavailable: %s", exc)
        return None


def _recompute_and_notify(db_factory, session_id: str, user_id: str, kafka_emit):
    """
    Recompute the session quality score from ML-updated TimelineBuckets and
    emit a notification.send event so the mobile app gets the refined result.
    """
    from app.models import SleepSession, TimelineBucket
    from app.scoring import compute_score, grade

    db = db_factory()
    try:
        session = db.query(SleepSession).filter(SleepSession.id == session_id).first()
        if not session:
            return

        buckets = (
            db.query(TimelineBucket)
            .filter(TimelineBucket.session_id == session_id)
            .all()
        )
        if not buckets:
            return

        snoring_buckets = [b for b in buckets if b.dominant_class == "snoring"]
        snore_ratio     = len(snoring_buckets) / len(buckets)
        avg_int         = (
            sum(b.avg_intensity for b in snoring_buckets) / len(snoring_buckets)
            if snoring_buckets else 0.0
        )
        max_int       = max((b.avg_intensity for b in buckets), default=0.0)
        interruptions = sum(b.snore_event_count for b in buckets)
        duration      = session.duration_minutes or 1

        score = compute_score(snore_ratio, avg_int, interruptions, duration)

        session.sleep_quality_score   = score
        session.sleep_quality_grade   = grade(score)
        session.snoring_duration_min  = int(duration * snore_ratio)
        session.snoring_percentage    = round(snore_ratio * 100, 1)
        session.snore_events_per_hour = round(interruptions / max(duration / 60, 0.1), 1)
        session.avg_snore_intensity   = round(avg_int, 1)
        session.max_snore_intensity   = round(max_int, 1)
        db.commit()

        kafka_emit("notification.send", {
            "user_id":             user_id,
            "session_id":          session_id,
            "type":                "session_ready",
            "sleep_quality_score": score,
            "sleep_quality_grade": grade(score),
            "snoring_percentage":  session.snoring_percentage,
        })

        _logger.info(
            "Session %s ML-refined score: %.1f (%s)", session_id, score, grade(score),
        )
    finally:
        db.close()
