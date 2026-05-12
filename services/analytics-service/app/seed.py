"""
Generates 30 days of realistic mock sleep data for a new user.
Called once per user on first analytics request.
"""
import uuid, random, math
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from app.models import SleepSession, TimelineBucket, SessionInsight, SeededUser

INSIGHT_TEMPLATES = [
    ("tip",     "Try sleeping on your side",
     "Side-sleeping reduces snoring by keeping your airway open. Use a pillow behind your back to stay in position."),
    ("tip",     "Avoid alcohol 3 hours before bed",
     "Alcohol relaxes throat muscles, significantly increasing snoring intensity. Tonight's data shows elevated intensity."),
    ("tip",     "Stay hydrated during the day",
     "Dehydration makes nasal secretions stickier, contributing to snoring. Aim for 8 glasses of water daily."),
    ("tip",     "Consider a humidifier",
     "Dry air irritates airways. A bedroom humidifier at 40–50% humidity can noticeably reduce snoring."),
    ("warning", "5 consecutive nights of elevated snoring",
     "Your snoring has been above average for 5 nights. Consider consulting a sleep specialist."),
    ("achievement", "7-night streak recorded!",
     "Great consistency! 7 nights of data gives us enough to identify meaningful patterns."),
    ("tip",     "Elevate your head slightly",
     "A slightly elevated pillow (10–15°) can prevent airway collapse. Try a wedge pillow tonight."),
    ("warning", "Peak snoring at 2–4 AM",
     "Your snoring intensifies in the early morning hours. This is common in REM sleep — try limiting screen time before bed."),
]

def _grade(score: float) -> str:
    if score >= 90: return "Excellent"
    if score >= 75: return "Good"
    if score >= 60: return "Fair"
    if score >= 40: return "Poor"
    return "Critical"

def _compute_score(snore_ratio: float, avg_intensity: float, interruptions: int, duration_min: int) -> float:
    gap_penalty = max(0.0, (360 - duration_min) / 360.0 * 15) if duration_min < 360 else 0
    raw = 100 - (snore_ratio * 40 + (avg_intensity / 100.0) * 25 + interruptions * 2 + gap_penalty)
    return round(max(0.0, min(100.0, raw)), 1)

def _make_timeline(session_id: str, duration_minutes: int, snore_ratio: float, rng: random.Random):
    buckets = []
    num = duration_minutes // 5
    for i in range(num):
        # snoring peaks in the middle of the night
        wave = math.sin(math.pi * i / max(num - 1, 1))
        base = rng.uniform(0, 80) * wave * snore_ratio * 2.5
        base = max(0, min(100, base))

        if base > 35:
            cls, intensity, count = "snoring", base, int(base / 12)
        elif base > 10:
            cls, intensity, count = "breathing", base * 0.25, 0
        else:
            cls, intensity, count = "silence", 0.0, 0

        buckets.append(TimelineBucket(
            id=str(uuid.uuid4()),
            session_id=session_id,
            bucket_index=i,
            offset_minutes=i * 5,
            avg_intensity=round(intensity, 1),
            dominant_class=cls,
            snore_event_count=count,
        ))
    return buckets

def seed_user(user_id: str, db: Session):
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
        score = _compute_score(snore_ratio, avg_int, interruptions, duration)

        session = SleepSession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            started_at=start,
            ended_at=end,
            duration_minutes=duration,
            status="complete",
            sleep_quality_score=score,
            sleep_quality_grade=_grade(score),
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

        for bucket in _make_timeline(session.id, duration, snore_ratio, rng):
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
