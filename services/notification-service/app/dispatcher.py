"""
Central dispatch logic — persists Notification record and fans out to push / email.
Called by both the Kafka consumer and internal service triggers.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

_logger = logging.getLogger(__name__)


def dispatch(
    *,
    user_id: str,
    notif_type: str,
    title: str,
    body: str,
    payload: Optional[dict] = None,
    channels: list,           # e.g. ["push", "in_app"] or ["push", "email", "in_app"]
    db,
    user_email: Optional[str] = None,
) -> str:
    """
    Persist a Notification and deliver it via the requested channels.

    Channels
    --------
    push    — FCM / APNs via push_client.send_push()
    email   — SendGrid via email_client.send_email() (requires user_email)
    in_app  — stored in DB only; surfaced by GET /notifications

    Returns the new Notification.id.
    """
    from app.models import Notification
    from app.push_client import send_push
    from app.email_client import send_email

    notif = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        body=body,
        payload=json.dumps(payload or {}),
        channel=",".join(channels),
    )
    db.add(notif)
    db.flush()   # get ID without full commit

    sent_at = None

    if "push" in channels:
        n = send_push(user_id, title, body, payload or {}, db)
        if n > 0:
            sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
            _logger.info("Push sent to %d token(s) for user %s", n, user_id)

    if "email" in channels and user_email:
        ok = send_email(user_email, title, f"<p>{body}</p>")
        if ok and sent_at is None:
            sent_at = datetime.now(timezone.utc).replace(tzinfo=None)

    if "in_app" in channels and sent_at is None:
        sent_at = datetime.now(timezone.utc).replace(tzinfo=None)

    notif.sent_at = sent_at
    db.commit()
    db.refresh(notif)
    return notif.id
