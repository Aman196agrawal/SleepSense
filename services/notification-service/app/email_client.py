"""
Email client — SendGrid transactional email.
When SENDGRID_API_KEY is not configured, logs and returns True (stub mode).
"""
import logging

_logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, html_body: str) -> bool:
    """Send a transactional email via SendGrid. Returns True on success or stub."""
    from app.config import settings
    if not settings.SENDGRID_API_KEY:
        _logger.debug("Email stub: '%s' → %s", subject, to_email)
        return True
    try:
        import httpx
        resp = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
            json={
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {
                    "email": settings.SENDGRID_FROM_EMAIL,
                    "name":  settings.SENDGRID_FROM_NAME,
                },
                "subject": subject,
                "content": [{"type": "text/html", "value": html_body}],
            },
            timeout=15.0,
        )
        return resp.status_code == 202
    except Exception as exc:
        _logger.warning("SendGrid send failed: %s", exc)
        return False
