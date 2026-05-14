"""
Kafka consumer — listens for insights.generate events from Analytics service.
Runs in a daemon thread from main.py lifespan.
"""
import json
import logging

_logger = logging.getLogger(__name__)


def run_consumer(db_factory, kafka_emit_fn):
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
        settings.KAFKA_INPUT_TOPIC,
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda v: json.loads(v.decode()),
        group_id=settings.KAFKA_GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )
    _logger.info("Insight consumer started on topic %s", settings.KAFKA_INPUT_TOPIC)

    for msg in consumer:
        payload = msg.value
        session_id = payload.get("session_id", "<unknown>")
        user_id    = payload.get("user_id")
        if not user_id:
            continue
        try:
            db = db_factory()
            try:
                _process(payload, user_id, session_id, db, kafka_emit_fn)
            finally:
                db.close()
        except Exception as exc:
            _logger.error("Failed to generate insights for session %s: %s", session_id, exc, exc_info=True)


def _process(payload: dict, user_id: str, session_id: str, db, kafka_emit_fn):
    from app.rules import evaluate_rules
    from app.models import SessionInsight
    from app.config import settings

    rule_insights = evaluate_rules(
        sleep_quality_score  = float(payload.get("sleep_quality_score", 50)),
        snore_ratio          = float(payload.get("snore_ratio", 0.0)),
        avg_snore_intensity  = float(payload.get("avg_snore_intensity", 0.0)),
        duration_minutes     = int(payload.get("duration_minutes", 480)),
        recent_scores        = payload.get("recent_scores", []),
        recent_durations     = payload.get("recent_durations", []),
        alcohol_units_today  = float(payload.get("alcohol_units_today", 0.0)),
        sleep_position       = payload.get("sleep_position"),
    )

    for ri in rule_insights:
        insight = SessionInsight(
            session_id   = session_id,
            user_id      = user_id,
            insight_type = ri["insight_type"],
            priority     = ri["priority"],
            title        = ri["title"],
            body         = ri["body"],
            action_url   = ri.get("action_url"),
        )
        db.add(insight)

    db.commit()
    _logger.info("Generated %d insight(s) for session %s", len(rule_insights), session_id)

    # Notify user for CHRONIC_SNORING
    for ri in rule_insights:
        if ri.get("rule_name") == "CHRONIC_SNORING":
            kafka_emit_fn(settings.KAFKA_NOTIFICATION_TOPIC, {
                "user_id":  user_id,
                "type":     "health_alert",
                "title":    ri["title"],
                "body":     ri["body"],
                "channels": ["push", "in_app"],
            })
