import json
import logging
import time
import urllib.error
import urllib.request

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from app.config import settings

bearer = HTTPBearer()
_logger = logging.getLogger(__name__)


# ── Lightweight TTL cache for inter-service user-existence checks ─────────────
# We don't want every analytics request to fan out to auth-service, so cache
# positive results for a short TTL. A revoked user keeps working for at most
# _USER_CHECK_TTL_SECONDS after deletion — short enough to be acceptable, long
# enough to avoid hammering the auth service.
_USER_CHECK_TTL_SECONDS = 60
_USER_CACHE_MAX = 10_000
_user_check_cache: dict[str, float] = {}


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def _user_exists_in_auth_service(user_id: str, bearer_token: str) -> bool:
    """Call auth-service /users/me to confirm the user still exists.

    Returns True when the auth service confirms the user, or when the auth
    service is unreachable (fail-open — analytics shouldn't go down because
    auth is down). Returns False only on a confirmed 401/404.
    """
    if not settings.AUTH_SERVICE_URL:
        # Not configured — skip the check entirely (single-process dev mode).
        return True

    cached = _user_check_cache.get(user_id)
    now = time.time()
    if cached and (now - cached) < _USER_CHECK_TTL_SECONDS:
        return True

    url = f"{settings.AUTH_SERVICE_URL.rstrip('/')}/users/me"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {bearer_token}"})
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                if len(_user_check_cache) >= _USER_CACHE_MAX:
                    # Evict oldest 10 % of entries to keep memory bounded
                    oldest = sorted(_user_check_cache.items(), key=lambda kv: kv[1])
                    for k, _ in oldest[:_USER_CACHE_MAX // 10]:
                        _user_check_cache.pop(k, None)
                _user_check_cache[user_id] = now
                return True
    except urllib.error.HTTPError as e:
        if e.code in (401, 404):
            return False
        _logger.warning("auth-service returned %s during user check", e.code, exc_info=True)
        return True  # fail-open on unexpected codes
    except Exception:
        _logger.warning("auth-service unreachable during user check", exc_info=True)
        return True  # fail-open on network errors

    return True


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload["sub"]
    if not _user_exists_in_auth_service(user_id, credentials.credentials):
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user_id
