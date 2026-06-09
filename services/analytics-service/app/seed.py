"""
Generates 30 days of realistic mock sleep data for a new user.
Called once per user on first analytics request.
"""
import logging
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import SleepSession, SessionInsight, SeededUser
from app.scoring import (
    INSIGHT_TEMPLATES,
    compute_score,
    grade,
    make_timeline,
)

# Backwards-compatibility: a couple of test files reach in for the private
# helpers under their old names. Re-export so those imports keep working.
_grade = grade
_compute_score = compute_score
_make_timeline = make_timeline

_logger = logging.getLogger(__name__)


def seed_user(user_id: str, db: Session) -> None:
    if db.query(SeededUser).filter(SeededUser.user_id == user_id).first():
        return  # already seeded

    rng = random.Random(user_id)  # deterministic per user
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for days_ago in range(30, 0, -1):
        if rng.random() < 0.18:  # ~18% nights skipped
            continue

        base_date = now - timedelta(days=days_ago)
        start = base_date.replace(hour=22, minute=rng.randint(0, 59), second=0, microsecond=0)
        duration = rng.randint(340, 510)
        end = start + timedelta(minutes=duration)

        # Scores trend upward over time (first nights worse, recent better)
        trend_factor = days_ago / 30.0  # 1.0 = oldest, 0.0 = newest
        snore_ratio = rng.uniform(0.05, 0.40) * (0.6 + trend_factor * 0.8)
        avg_int = rng.uniform(25, 75) * (0.6 + trend_factor * 0.7)
        interruptions = rng.randint(0, 12)

        snore_ratio = round(min(snore_ratio, 0.95), 3)
        avg_int = round(min(avg_int, 100), 1)
        max_int = round(min(avg_int * rng.uniform(1.2, 1.8), 100), 1)
        score = compute_score(snore_ratio, avg_int, interruptions, duration)

        session = SleepSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            started_at=start,
            ended_at=end,
            duration_minutes=duration,
            status="complete",
            sleep_quality_score=score,
            sleep_quality_grade=grade(score),
            snoring_duration_min=int(duration * snore_ratio),
            snoring_percentage=round(snore_ratio * 100, 1),
            snore_events_per_hour=round(interruptions / (duration / 60), 1),
            avg_snore_intensity=avg_int,
            max_snore_intensity=max_int,
            peak_snoring_hour=rng.randint(0, 4),
            total_chunks=duration // 30,
            processed_chunks=duration // 30,
        )
        db.add(session)

        for bucket in make_timeline(session.id, duration, snore_ratio, rng):
            db.add(bucket)

        tmpl = rng.choice(INSIGHT_TEMPLATES)
        db.add(SessionInsight(
            id=str(uuid.uuid4()),
            session_id=session.id,
            user_id=user_id,
            insight_type=tmpl[0],
            priority=rng.randint(1, 10),
            title=tmpl[1],
            body=tmpl[2],
        ))

    db.add(SeededUser(user_id=user_id))
    db.commit()
    _logger.info("Seeded 30-day mock history for user %s", user_id)
