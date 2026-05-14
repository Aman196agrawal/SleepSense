import json
import logging

_logger = logging.getLogger(__name__)
_redis = None


def get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis as _r
        from app.config import settings
        if not settings.REDIS_URL:
            return None
        _redis = _r.from_url(settings.REDIS_URL, decode_responses=True)
        _redis.ping()
        return _redis
    except Exception as exc:
        _logger.debug("Redis unavailable: %s", exc)
        return None


def set_session_status(session_id: str, data: dict) -> None:
    r = get_redis()
    if r:
        try:
            r.setex(f"session:status:{session_id}", 86400, json.dumps(data))
        except Exception:
            pass


def get_session_status(session_id: str) -> dict | None:
    r = get_redis()
    if r:
        try:
            val = r.get(f"session:status:{session_id}")
            return json.loads(val) if val else None
        except Exception:
            pass
    return None
