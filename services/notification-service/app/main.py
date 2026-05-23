import logging
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.database import SessionLocal, init_db
from app.dispatcher import dispatch

_logger = logging.getLogger(__name__)


def _run_weekly_summary_job():
    """Send weekly summary push/email every Monday ~8 AM UTC (FR-NOTIF-002)."""
    while True:
        now = datetime.now(timezone.utc)
        # Monday = 0; wait until next Monday 08:00 UTC
        days_until_monday = (7 - now.weekday()) % 7 or 7
        next_run = now.replace(hour=8, minute=0, second=0, microsecond=0)
        if now.weekday() != 0 or now.hour >= 8:
            from datetime import timedelta
            next_run = next_run + timedelta(days=days_until_monday)
        wait_secs = max(0, (next_run - now).total_seconds())
        _logger.info("Weekly summary job sleeping %.0f s until %s", wait_secs, next_run.isoformat())
        time.sleep(wait_secs)

        try:
            db = SessionLocal()
            try:
                _fire_weekly_summaries(db)
            finally:
                db.close()
        except Exception:
            _logger.error("Weekly summary job failed", exc_info=True)


def _fire_weekly_summaries(db):
    """Dispatch a weekly summary notification to each user who has recent sessions."""
    from app.models import Notification
    # Fetch distinct user_ids from notification log (proxy for active users)
    user_ids = [r[0] for r in db.query(Notification.user_id).distinct().all()]
    for uid in user_ids:
        try:
            dispatch(
                user_id=uid,
                notif_type="weekly_summary",
                title="Your weekly sleep report is ready.",
                body="Check your sleep trends and insights for the past week.",
                payload={"screen": "History"},
                channels=["push", "in_app"],
                db=db,
            )
        except Exception:
            _logger.warning("Weekly summary dispatch failed for user %s", uid, exc_info=True)
    _logger.info("Weekly summary sent to %d users", len(user_ids))


def _run_bedtime_reminder_job():
    """Send bedtime reminders every minute to users whose reminder time matches now (FR-GOAL-001).

    Checks once per minute. Matches when the current HH:MM (UTC) equals the stored
    bedtime_reminder_time. Users store their reminder time in HH:MM format via
    PATCH /users/me with bedtime_reminder_time.
    """
    from app.config import settings as _s
    AUTH_SERVICE_URL = _s.AUTH_SERVICE_URL

    while True:
        time.sleep(60)
        if not AUTH_SERVICE_URL:
            continue
        now_hhmm = datetime.now(timezone.utc).strftime("%H:%M")
        try:
            import urllib.request
            with urllib.request.urlopen(
                f"{AUTH_SERVICE_URL.rstrip('/')}/internal/users/with-reminder/{now_hhmm}",
                timeout=5,
            ) as resp:
                import json
                users = json.loads(resp.read())
        except Exception:
            continue  # auth-service unreachable — skip this minute

        db = SessionLocal()
        try:
            for user in users:
                try:
                    dispatch(
                        user_id=user["id"],
                        notif_type="bedtime_reminder",
                        title="Time to start tonight's recording.",
                        body="Place your phone nearby and tap Start Recording before you sleep.",
                        payload={"screen": "Record"},
                        channels=["push"],
                        db=db,
                    )
                except Exception:
                    _logger.warning("Bedtime reminder failed for user %s", user.get("id"), exc_info=True)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()

    from app.kafka_consumer import run_consumer
    t = threading.Thread(
        target=run_consumer,
        args=(SessionLocal, dispatch),
        daemon=True,
        name="notif-kafka-consumer",
    )
    t.start()

    threading.Thread(
        target=_run_weekly_summary_job,
        daemon=True,
        name="notif-weekly-summary",
    ).start()

    threading.Thread(
        target=_run_bedtime_reminder_job,
        daemon=True,
        name="notif-bedtime-reminder",
    ).start()

    yield


app = FastAPI(
    title="SleepSense Notification Service",
    version="1.0.0",
    lifespan=lifespan,
)

from app.routes import notifications, device_tokens  # noqa: E402

app.include_router(notifications.router,  prefix="/notifications",  tags=["Notifications"])
app.include_router(device_tokens.router,  prefix="/device-tokens",  tags=["Device Tokens"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}
