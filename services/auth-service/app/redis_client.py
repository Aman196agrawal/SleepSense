import redis as _redis
from app.config import settings

_client: _redis.Redis | None = None

def get_redis() -> _redis.Redis | None:
    """Return Redis client if REDIS_URL is configured, else None (falls back to DB)."""
    global _client
    if not settings.REDIS_URL:
        return None
    if _client is None:
        _client = _redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client
