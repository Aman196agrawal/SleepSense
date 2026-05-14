"""
Push notification client — FCM (Android) and APNs (iOS).
When credentials are not configured the functions log and return True (stub mode).
"""
import logging

_logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"fcm", "apns"}


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


def _send_apns(token: str, title: str, body: str, payload: dict) -> bool:
    from app.config import settings
    if not settings.APNS_KEY_ID:
        _logger.debug("APNs stub: '%s' → %s…", title, token[:8])
        return True
    # Production: HTTP/2 + JWT via APNS_KEY_FILE — not implemented for MVP
    _logger.warning("APNs production credentials present but HTTP/2 client not wired — stub")
    return True
