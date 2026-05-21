"""
Pure scoring/timeline utilities shared between the seeder and the
session-lifecycle routes. Extracted out of `seed.py` so that runtime code
doesn't import private (`_`-prefixed) helpers from a seeder module.
"""
import math
import random
import uuid
from typing import List

from app.models import TimelineBucket


# Canonical insight templates used both during seeding (random pick per day)
# and when ending a real session without a more specific pattern insight.
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


def grade(score: float) -> str:
    """Map a numeric sleep score (0–100) to a coarse letter-grade-style label."""
    if score >= 90: return "Excellent"
    if score >= 75: return "Good"
    if score >= 60: return "Fair"
    if score >= 40: return "Poor"
    return "Critical"


def compute_score(
    snore_ratio: float,
    avg_intensity: float,
    interruptions: int,
    duration_min: int,
) -> float:
    """Combine snoring %, intensity, interruption count and duration into 0–100."""
    gap_penalty = max(0.0, (360 - duration_min) / 360.0 * 15) if duration_min < 360 else 0
    raw = 100 - (snore_ratio * 40 + (avg_intensity / 100.0) * 25 + interruptions * 2 + gap_penalty)
    return round(max(0.0, min(100.0, raw)), 1)


def make_timeline(
    session_id: str,
    duration_minutes: int,
    snore_ratio: float,
    rng: random.Random,
) -> List[TimelineBucket]:
    """Synthesise 5-minute timeline buckets for a session with no real chunks."""
    buckets: List[TimelineBucket] = []
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
