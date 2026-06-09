"""
Push notification client — FCM (Android) and APNs (iOS).
When credentials are not configured the functions log and return True (stub mode).
"""
import logging
import time

_logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"fcm", "apns"}

# APNs JWT cache — tokens are valid for 60 min; reuse to avoid re-signing every push
_apns_jwt_cache: dict = {}   # {"token": str, "issued_at": float}
_APNS_JWT_TTL = 3000         # 50 min (Apple max is 60 min)


def send_push(user_id: str, title: str, body: str, payload: dict, db) -> int:
    """Send push to every registered device token for user_id.
    Returns the number of tokens targeted (including stubs)."""
    from app.models import DeviceToken
    tokens = db.query(DeviceToken).filter(DeviceToken.user_id == user_id).all()
    if not tokens:
        return 0
    sent = 0
    for dt in tokens:
        if dt.platform == "fcm":
            ok = _send_fcm(dt.token, title, body, payload)
        else:
            ok = _send_apns(dt.token, title, body, payload)
        if ok:
            sent += 1
    return sent


def _send_fcm(token: str, title: str, body: str, payload: dict) -> bool:
    from app.config import settings
    if not settings.FCM_SERVER_KEY:
        _logger.debug("FCM stub: '%s' → %s…", title, token[:8])
        return True
    try:
        import httpx
        resp = httpx.post(
            "https://fcm.googleapis.com/fcm/send",
            headers={"Authorization": f"key={settings.FCM_SERVER_KEY}"},
            json={
                "to": token,
                "notification": {"title": title, "body": body},
                "data": payload,
            },
            timeout=10.0,
        )
        return resp.status_code == 200
    except Exception as exc:
        _logger.warning("FCM send failed: %s", exc)
        return False


def _make_apns_jwt() -> str:
    """Build a signed ES256 JWT for APNs provider authentication.
    Caches the token for up to 50 minutes to avoid signing on every push.
    """
    from app.config import settings
    now = time.time()
    cached = _apns_jwt_cache
    if cached.get("token") and (now - cached.get("issued_at", 0)) < _APNS_JWT_TTL:
        return cached["token"]

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.backends import default_backend
        import base64
        import json

        with open(settings.APNS_KEY_FILE, "rb") as f:
            private_key = load_pem_private_key(f.read(), password=None, backend=default_backend())

        header  = {"alg": "ES256", "kid": settings.APNS_KEY_ID}
        payload = {"iss": settings.APNS_TEAM_ID, "iat": int(now)}

        def _b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        header_b64  = _b64(json.dumps(header).encode())
        payload_b64 = _b64(json.dumps(payload).encode())
        signing_input = f"{header_b64}.{payload_b64}".encode()

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        signature = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
        sig_b64 = _b64(signature)

        token = f"{header_b64}.{payload_b64}.{sig_b64}"
        _apns_jwt_cache["token"]     = token
        _apns_jwt_cache["issued_at"] = now
        return token
    except Exception as exc:
        raise RuntimeError(f"APNs JWT signing failed: {exc}") from exc


def _send_apns(token: str, title: str, body: str, payload: dict) -> bool:
    from app.config import settings
    if not settings.APNS_KEY_ID or not settings.APNS_KEY_FILE:
        _logger.debug("APNs stub: '%s' → %s…", title, token[:8])
        return True
    try:
        import httpx
        jwt_token = _make_apns_jwt()
        apns_host = "https://api.push.apple.com"
        url = f"{apns_host}/3/device/{token}"
        resp = httpx.post(
            url,
            headers={
                "Authorization":  f"bearer {jwt_token}",
                "apns-topic":     settings.APNS_TOPIC,
                "apns-push-type": "alert",
                "apns-priority":  "10",
            },
            json={
                "aps": {
                    "alert": {"title": title, "body": body},
                    "sound": "default",
                },
                **payload,
            },
            http2=True,
            timeout=10.0,
        )
        if resp.status_code != 200:
            _logger.warning("APNs rejected push for %s…: %s %s", token[:8], resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:
        _logger.warning("APNs send failed: %s", exc)
        return False
