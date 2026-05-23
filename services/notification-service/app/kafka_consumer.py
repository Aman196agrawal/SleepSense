"""
Kafka consumer — listens for session.ended and notification.send events.
Runs in a daemon thread started from main.py lifespan.
"""
import json
import logging

_logger = logging.getLogger(__name__)


def run_consumer(db_factory, dispatcher_fn):
    """Blocking consumer loop — exits cleanly if Kafka is unavailable."""
    from app.config import settings

    try:
        from kafka import KafkaConsumer
    except ImportError:
        _logger.warning("kafka-python not installed — consumer disabled")
        return

    if not settings.KAFKA_BOOTSTRAP_SERVERS:
        _logger.info("KAFKA_BOOTSTRAP_SERVERS not set — consumer disabled")
        return

    consumer = KafkaConsumer(
        settings.KAFKA_SESSION_ENDED_TOPIC,
        settings.KAFKA_NOTIFICATION_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode()),
        group_id=settings.KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    _logger.info(
        "Notification consumer started on topics: %s, %s",
        settings.KAFKA_SESSION_ENDED_TOPIC,
        settings.KAFKA_NOTIFICATION_TOPIC,
    )

    for msg in consumer:
        topic   = msg.topic
        payload = msg.value
        try:
            db = db_factory()
            try:
                if topic == settings.KAFKA_SESSION_ENDED_TOPIC:
                    _handle_session_ended(payload, db, dispatcher_fn)
                elif topic == settings.KAFKA_NOTIFICATION_TOPIC:
                    _handle_notification_send(payload, db, dispatcher_fn)
            finally:
                db.close()
        except Exception as exc:
            _logger.error("Consumer error on topic %s: %s", topic, exc, exc_info=True)


def _can_send_health_alert(user_id: str, db) -> bool:
    """Return True only if no health alert was sent in the last 7 days (FR-NOTIF-003)."""
    from datetime import datetime, timezone, timedelta
    from app.models import Notification
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    recent = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.type == "health_alert",
        Notification.created_at >= cutoff,
    ).first()
    return recent is None


def _handle_session_ended(payload: dict, db, dispatcher_fn):
    """Fire a sleep_report_ready push when a session completes."""
    if payload.get("status") != "complete":
        return
    user_id    = payload.get("user_id")
    session_id = payload.get("session_id", "")
    if not user_id:
        return
    score = payload.get("sleep_quality_score")
    snore = payload.get("snoring_percentage")
    body  = (
        f"Sleep score: {int(score)}/100 · Snoring: {int(snore or 0)}% of the night."
        if score is not None
        else "Tap to see your full sleep report."
    )
    dispatcher_fn(
        user_id=user_id,
        notif_type="sleep_report_ready",
        title="Your sleep report is ready.",
        body=body,
        payload={"session_id": session_id, "screen": "SessionDetail"},
        channels=["push", "in_app"],
        db=db,
    )
    _logger.info("sleep_report_ready sent for session %s", session_id)

    # Health alert: fire at most once per 7 days when CHRONIC_SNORING is detected
    if score is not None and score < 50 and _can_send_health_alert(user_id, db):
        dispatcher_fn(
            user_id=user_id,
            notif_type="health_alert",
            title="Recurring poor sleep detected",
            body="5+ consecutive nights of poor sleep detected. Consider consulting a sleep specialist.",
            payload={"screen": "Insights"},
            channels=["push", "in_app"],
            db=db,
        )
        _logger.info("health_alert sent for user %s", user_id)


def _handle_notification_send(payload: dict, db, dispatcher_fn):
    """Generic dispatch — used by Insight Engine and other services."""
    user_id = payload.get("user_id")
    if not user_id:
        return
    dispatcher_fn(
        user_id=user_id,
        notif_type=payload.get("type", "generic"),
        title=payload.get("title", ""),
        body=payload.get("body", ""),
        payload=payload.get("payload"),
        channels=payload.get("channels", ["in_app"]),
        db=db,
        user_email=payload.get("user_email"),
    )
