"""
Redis client for inference result caching (SRS FR-INF-003).
Caches XGBoost regressor outputs keyed by SHA-256 of the feature vector.
TTL: 7 days — identical audio snippets rarely need re-inference.
"""
import hashlib
import logging

_logger = logging.getLogger(__name__)

_CACHE_TTL = 7 * 24 * 3600  # 7 days in seconds

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        from app.config import settings
        if not settings.REDIS_URL:
            return None
        import redis
        client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        client.ping()
        _redis_client = client
        return _redis_client
    except Exception as exc:
        _logger.debug("Redis unavailable: %s", exc)
        return None


def _feature_key(features) -> str:
    import numpy as np
    arr = np.asarray(features, dtype=np.float32)
    digest = hashlib.sha256(arr.tobytes()).hexdigest()
    return f"inference:cache:{digest}"


def get_inference_cache(features) -> float | None:
    """Return cached intensity for a feature vector, or None on miss/error."""
    r = _get_redis()
    if not r:
        return None
    try:
        val = r.get(_feature_key(features))
        return float(val) if val is not None else None
    except Exception as exc:
        _logger.debug("Redis cache get failed: %s", exc)
        return None


def set_inference_cache(features, intensity: float) -> None:
    """Store intensity for a feature vector with 7-day TTL."""
    r = _get_redis()
    if not r:
        return
    try:
        r.setex(_feature_key(features), _CACHE_TTL, str(intensity))
    except Exception as exc:
        _logger.debug("Redis cache set failed: %s", exc)


def check_connectivity() -> bool:
    """Return True if Redis is reachable."""
    try:
        r = _get_redis()
        return r is not None
    except Exception:
        return False
